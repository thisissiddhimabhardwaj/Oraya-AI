"""Google error classification and process-local quota cooldowns.

Raw provider payloads are inspected in memory only. Diagnostics are an allowlist;
provider messages, headers, project identifiers and private content are never logged.
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math
import re
from threading import BoundedSemaphore, RLock
import time
from zoneinfo import ZoneInfo


def status_code(exc):
    value = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    if value is None:
        value = getattr(getattr(exc, 'response', None), 'status_code', None)
    if value is None and any(term in type(exc).__name__.lower() for term in ('timeout', 'readtimeout', 'connecttimeout')):
        return 504
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def seconds(value):
    try:
        if isinstance(value, dict):
            result = float(value.get('seconds', 0)) + float(value.get('nanos', 0))/1e9
        else:
            result = float(str(value).removesuffix('s'))
        return max(0, result) if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def retry_after(value, now=None):
    numeric = seconds(value)
    if numeric is not None:
        return numeric
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return max(0, (date - (now or datetime.now(timezone.utc))).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def daily_reset_seconds():
    # Gemini RPD resets at midnight Pacific, including DST transitions.
    now = datetime.now(ZoneInfo('America/Los_Angeles'))
    reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return reset.timestamp() - now.timestamp()


def safe_identifier(value):
    value = str(value)
    return value if len(value) <= 180 and re.fullmatch(r'[A-Za-z0-9_./:-]+', value) and not re.search(r'AIza[A-Za-z0-9_-]{20,}',value) else '[redacted]'


@dataclass
class QuotaInfo:
    category: str = 'UNKNOWN_QUOTA_LIMIT'
    scope: str = 'model'
    http_status: int | None = None
    api_status: str = ''
    retry_delay: float | None = None
    retry_after: float | None = None
    metrics: list[dict] = field(default_factory=list)
    source_model: str | None = None

    @property
    def delay(self):
        values = [v for v in (self.retry_delay, self.retry_after) if v is not None]
        return max(values) if values else None

    def diagnostics(self):
        # Never return the arbitrary original error.message or opaque details.
        return {'http_status': self.http_status, 'api_status': self.api_status,
                'category': self.category, 'scope': self.scope,
                'retry_delay_seconds': self.retry_delay, 'retry_after_seconds': self.retry_after,
                'quota_metrics': self.metrics, 'source_model': self.source_model}


def classify(exc):
    response = getattr(exc, 'response', None)
    payload = getattr(exc, 'response_json', None) or getattr(exc, 'details', None)
    if not isinstance(payload, (dict, list)) and response is not None:
        try:
            payload = response.json()
        except Exception:
            payload = {}
    if isinstance(payload, list):
        payload = payload[0] if len(payload) == 1 and isinstance(payload[0], dict) else {'details': payload}
    payload = payload if isinstance(payload, dict) else {}
    error = payload.get('error', payload)
    error = error if isinstance(error, dict) else {}
    message = str(error.get('message', getattr(exc, 'message', ''))).lower()
    state = str(error.get('status', ''))
    info = QuotaInfo(http_status=status_code(exc), api_status=state if state in {
        'RESOURCE_EXHAUSTED','UNAVAILABLE','PERMISSION_DENIED','INVALID_ARGUMENT',
        'UNAUTHENTICATED','NOT_FOUND','FAILED_PRECONDITION','INTERNAL'} else '')
    headers = getattr(response, 'headers', {}) or {}
    info.retry_after = retry_after(headers.get('retry-after') or headers.get('Retry-After'))
    if info.http_status != 429:
        info.category = {401:'AUTHENTICATION',403:'AUTHORIZATION',404:'MODEL_UNAVAILABLE',
                         500:'TEMPORARY_FAILURE',502:'TEMPORARY_FAILURE',
                         503:'TEMPORARY_FAILURE',504:'GATEWAY_TIMEOUT'}.get(info.http_status,'PROVIDER_ERROR')
    if info.http_status == 504 or (info.http_status is None and any(term in type(exc).__name__.lower() for term in ('timeout', 'readtimeout', 'connecttimeout'))):
        info.http_status = 504
        info.category = 'GATEWAY_TIMEOUT'
        info.api_status = 'DEADLINE_EXCEEDED'
    # A confirmed generation 404 is never evidence of a billing/quota problem.
    if info.http_status == 404:
        return info
    details = error.get('details', [])
    if not isinstance(details, list):
        details = []
    violations = []
    reasons = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        kind = str(detail.get('@type', ''))
        if kind.endswith('RetryInfo'):
            delay = seconds(detail.get('retryDelay', detail.get('retry_delay')))
            if delay is not None:
                info.retry_delay = max(info.retry_delay or 0, delay)
        if kind.endswith('QuotaFailure'):
            items=detail.get('violations', [])
            if isinstance(items,list):violations.extend(v for v in items if isinstance(v,dict))
        if kind.endswith('ErrorInfo'):
            reasons.append(str(detail.get('reason', '')).lower())
            metadata=detail.get('metadata', {})
            if isinstance(metadata,dict) and (metadata.get('quota_metric') or metadata.get('quota_limit')):
                violations.append({'quotaMetric':metadata.get('quota_metric',''),
                                   'quotaId':metadata.get('quota_limit',''),
                                   'quotaDimensions':{'model':metadata['model']} if metadata.get('model') else {}})
    text = ' '.join([message, *reasons])
    # Google quota messages routinely say "check your plan and billing details".
    # Only explicit restrictions, not the word billing itself, justify project blocking.
    billing = any(term in text for term in (
        'billing_disabled', 'billing_not_enabled', 'billing disabled',
        'billing is disabled', 'billing account disabled', 'billing account is disabled',
        'billing restriction', 'billing spend restriction', 'spending limit', 'spend limit',
        'payment required', 'insufficient credits', 'credit balance exhausted', 'budget exceeded'))
    shared = any(term in text for term in ('project-wide', 'project wide', 'across all models', 'shared project'))
    has_model_quota = False
    has_shared_quota = False
    categories = []
    for violation in violations:
        metric = str(violation.get('quotaMetric', ''))
        quota_id = str(violation.get('quotaId', ''))
        dimensions = violation.get('quotaDimensions', {})
        dimensions = dimensions if isinstance(dimensions, dict) else {}
        identity = (metric + ' ' + quota_id).lower()
        per_model = bool(dimensions.get('model')) or 'permodel' in identity or 'per_model' in identity
        per_project = 'perproject' in identity or 'per_project' in identity
        # A project identifier alone does not prove the limit is shared across models.
        has_model_quota = has_model_quota or per_model
        if per_project and not per_model:
            has_shared_quota = True
        dims = {k: safe_identifier(v) for k,v in dimensions.items() if k in ('model','location')}
        value=str(violation.get('quotaValue',''))
        info.metrics.append({'metric': safe_identifier(metric), 'quota_id': safe_identifier(quota_id),
                             'dimensions': dims, 'quota_value': value if re.fullmatch(r'[0-9.]+',value) else None})
        if any(x in identity for x in ('perday','per_day','daily')):
            categories.append('RPD')
        elif 'token' in identity and any(x in identity for x in ('perminute','per_minute')):
            categories.append('TPM')
        elif 'request' in identity and any(x in identity for x in ('perminute','per_minute')):
            categories.append('RPM')
    if has_model_quota or has_shared_quota:
        shared = has_shared_quota
    # Structured quota violations override generic plan/billing guidance.
    explicit_billing_reason=any(r in {'billing_disabled','billing_not_enabled','billing_account_disabled','insufficient_credits','budget_exceeded'} for r in reasons)
    if explicit_billing_reason or (billing and not violations):
        info.category, info.scope = 'BILLING_RESTRICTION', 'project'
    else:
        if 'RPD' in categories or 'daily quota' in text or 'requests per day' in text:
            info.category = 'DAILY_QUOTA_EXHAUSTED'
        elif 'TPM' in categories or 'tokens per minute' in text:
            info.category = 'TPM'
        elif 'RPM' in categories or 'requests per minute' in text:
            info.category = 'RPM'
        elif any(term in text for term in ('capacity', 'overloaded', 'temporarily throttled')):
            info.category = 'TEMPORARY_CAPACITY'
        if shared:
            info.scope = 'project'
            if info.category == 'UNKNOWN_QUOTA_LIMIT':
                info.category = 'PROJECT_QUOTA_EXHAUSTED'
    return info


# Bounded semaphore allows concurrent calls without false admission timeouts. Waiting requests
# observe a quota cooldown before sending anything; a bounded acquire allows local fallback.
cloud_gate = BoundedSemaphore(4)
_state_lock = RLock()
_cooldowns = {}
_timeout_streaks: dict[str, int] = {}


def consecutive_timeouts(model: str) -> int:
    with _state_lock:
        return _timeout_streaks.get(model, 0)


def record_timeout(model: str) -> int:
    with _state_lock:
        streak = _timeout_streaks.get(model, 0) + 1
        _timeout_streaks[model] = streak
        return streak


def record_success(model: str) -> None:
    with _state_lock:
        _timeout_streaks.pop(model, None)


def cooldown(model):
    with _state_lock:
        now = time.monotonic()
        for key in list(_cooldowns):
            if _cooldowns[key][0] <= now:
                del _cooldowns[key]
        project=[v for k,v in _cooldowns.items() if k[:2]==('gemini','project')]
        own=[v for k,v in _cooldowns.items() if k[:3]==('gemini','model',model)]
        return max(project or own, key=lambda v:v[0], default=None)


def exhaust(model, info, default_seconds=60):
    duration = max(default_seconds, info.delay or 0)
    if info.category == 'DAILY_QUOTA_EXHAUSTED':
        duration = info.delay if info.delay is not None else daily_reset_seconds()
    elif info.category == 'BILLING_RESTRICTION':
        duration = max(300, info.delay or 0)
    elif info.category == 'GATEWAY_TIMEOUT':
        with _state_lock:
            streak = _timeout_streaks.get(model, 1)
        if streak <= 1:
            duration = max(30.0, info.delay or 0)
        elif streak == 2:
            duration = max(120.0, info.delay or 0)
        else:
            duration = max(300.0, info.delay or 0)
    identity=tuple(sorted((m.get('metric',''),m.get('quota_id',''),tuple(sorted(m.get('dimensions',{}).items()))) for m in info.metrics))
    key = ('gemini', info.scope, None if info.scope=='project' else model, identity)
    info=replace(info, source_model=model)
    with _state_lock:
        previous = _cooldowns.get(key, (0, None))[0]
        _cooldowns[key] = (max(previous, time.monotonic()+duration), info)
    return duration


def clear():
    """Reset process state for isolated deterministic tests."""
    with _state_lock:
        _cooldowns.clear()
        _timeout_streaks.clear()
