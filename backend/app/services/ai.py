"""Shared Gemini/Ollama gateway with quota-aware bounded failover.

Rules enforced here:
  * the API key never leaves the server
  * production calls fail explicitly when the configured provider is unavailable
  * provider failures never produce fabricated success
  * results identify the producing mode; configuration also reports unavailable services
"""
from __future__ import annotations

import json
import logging
import re
import time, random
from contextvars import ContextVar
import httpx
import jsonschema
from datetime import datetime, timezone
from typing import Any
from threading import RLock
from collections.abc import Mapping
from pathlib import Path
import traceback
import inspect

from ..config import settings
from . import ai_quota as quota

logger = logging.getLogger("oraya.ai")

_client = None
_client_lock = RLock()


class AIError(RuntimeError):
    def __init__(self,message,code="provider_unavailable",status=503):
        super().__init__(message);self.code=code;self.status=status


class GeminiOutputError(AIError):
    """Successful transport or SDK parsing did not produce a usable answer."""
    def __init__(self, message, category, metadata=None, *, allow_fallback=True):
        super().__init__(message, "provider_output", 502)
        self.category=category
        self.metadata=metadata or {}
        self.allow_fallback=allow_fallback


def sanitized_location(exc):
    root=exc
    while root.__cause__ is not None:
        root=root.__cause__
    frames=traceback.extract_tb(root.__traceback__)
    frame=frames[-1] if frames else None
    return {"exception_class":type(root).__name__,
            "location":f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" if frame else None}


def _field(obj, name, default=None):
    if isinstance(obj, Mapping):
        camel=name.split('_')[0]+''.join(p.title() for p in name.split('_')[1:])
        return obj.get(name, obj.get(camel, default))
    if obj is None:return default
    try:
        return getattr(obj,name)
    except AttributeError:
        # getattr(..., default) hides AttributeError raised *inside* SDK
        # descriptors. Preserve that parsing exception and its real location.
        marker=object()
        if inspect.getattr_static(obj,name,marker) is not marker:raise
        return default


def _enum_name(value):
    from google.genai import types
    allowed={v.value for v in types.FinishReason} | {
        "BLOCKED_REASON_UNSPECIFIED","SAFETY","OTHER","BLOCKLIST",
        "PROHIBITED_CONTENT","IMAGE_SAFETY","MODEL_ARMOR"}
    value=getattr(value,"value",value)
    token=str(value).split('.')[-1] if value is not None else None
    return token if token in allowed else "UNKNOWN" if token else None


def extract_gemini_text(response):
    """Read candidate parts directly; never depend on SDK response.text helpers.

    Metadata contains only counts and allowlisted enums, never part contents,
    thought text, tool names/arguments, provider messages or HTTP headers.
    """
    meta={"response_type":type(response).__name__}
    try:
        usage=_field(response,"usage_metadata")
        meta["token_counts"]={name:value if isinstance(value,int) else None for name in (
            "prompt_token_count","candidates_token_count","thoughts_token_count","total_token_count")
            for value in [_field(usage,name)]}
        candidates=_field(response,"candidates") or []
        if not isinstance(candidates,(list,tuple)):
            raise TypeError("Invalid candidate collection")
        feedback=_field(response,"prompt_feedback")
        prompt_block=_enum_name(_field(feedback,"block_reason"))
        meta.update(candidate_count=len(candidates),prompt_block=prompt_block,
                    afc_history_count=len(_field(response,"automatic_function_calling_history") or []),candidates=[])
        results=[]
        blocked_reasons={"SAFETY","RECITATION","BLOCKLIST","PROHIBITED_CONTENT","SPII",
                         "IMAGE_SAFETY","IMAGE_PROHIBITED_CONTENT","MODEL_ARMOR"}
        for candidate in candidates:
            finish=_enum_name(_field(candidate,"finish_reason"))
            parts=_field(_field(candidate,"content"),"parts") or []
            if not isinstance(parts,(list,tuple)):
                raise TypeError("Invalid part collection")
            texts=[];thoughts=0;functions=0
            for part in parts:
                functions+=int(_field(part,"function_call") is not None)
                if _field(part,"thought") is True:
                    thoughts+=1;continue
                text=_field(part,"text")
                if isinstance(text,str):texts.append(text)
            blocked=finish in blocked_reasons or any(_field(r,"blocked") is True for r in (_field(candidate,"safety_ratings") or []))
            text=''.join(texts).strip()
            meta["candidates"].append({"finish_reason":finish,"part_count":len(parts),
                "text_part_count":len(texts),"text_char_count":len(text),
                "thought_part_count":thoughts,"function_call_count":functions,"safety_blocked":blocked})
            results.append((text,finish,blocked,functions))
        logger.info("provider=gemini stage=response_structure metadata=%s",meta)
        if prompt_block not in (None,"BLOCKED_REASON_UNSPECIFIED"):
            raise GeminiOutputError("Gemini blocked this request; no answer was returned", "SAFETY_BLOCK",meta,allow_fallback=False)
        # Choose a complete, safe text candidate. A bad first candidate must not
        # hide a valid alternative candidate; thoughts are never student answers.
        for text,finish,blocked,functions in results:
            if text and not blocked and finish in (None,"STOP","FINISH_REASON_UNSPECIFIED"):
                return text
        if any(blocked for _,_,blocked,_ in results):
            raise GeminiOutputError("Gemini blocked this response; no answer was returned", "SAFETY_BLOCK",meta,allow_fallback=False)
        if any(finish=="MAX_TOKENS" for _,finish,_,_ in results):
            raise GeminiOutputError("Gemini response was truncated; incomplete output was rejected", "OUTPUT_TRUNCATED",meta)
        if any(functions or finish in ("MALFORMED_FUNCTION_CALL","UNEXPECTED_TOOL_CALL","TOO_MANY_TOOL_CALLS") for _,finish,_,functions in results):
            raise GeminiOutputError("Gemini requested a tool that this text endpoint does not provide", "UNEXPECTED_FUNCTION_CALL",meta)
        if any(text for text,_,_,_ in results):
            raise GeminiOutputError("Gemini did not finish a usable text answer", "INCOMPLETE_RESPONSE",meta)
        raise GeminiOutputError("Gemini returned no non-empty answer text", "EMPTY_RESPONSE",meta)
    except GeminiOutputError:
        raise
    except Exception as exc:
        raise GeminiOutputError("The Gemini SDK response could not be parsed", "SDK_RESPONSE_PARSE_ERROR",meta) from exc


def provider_error(exc):
    if isinstance(exc,AIError):return exc
    code=getattr(exc,'code',None) or getattr(exc,'status_code',None)
    if code in (401,403):return AIError('The AI provider rejected its credentials. Ask your ORAYA administrator to check the connection.','provider_auth',502)
    if code==404:return AIError('The configured AI model is unavailable. Check the backend model setting.','provider_model',502)
    if code==429:return AIError('The AI provider is rate-limiting requests. Wait a moment and retry.','provider_rate_limit',503)
    if 'timeout' in type(exc).__name__.lower():return AIError('The AI provider took too long. Please retry.','provider_timeout',504)
    if isinstance(exc,(json.JSONDecodeError,ValueError,jsonschema.ValidationError)):return AIError('The AI returned an invalid response. Please retry.','provider_output',502)
    return AIError('The AI provider is unavailable. Please retry after checking the connection.')


def _get_client():
    global _client
    if not settings.gemini_enabled:
        return None
    if _client is not None:
        return _client
    try:
        from google import genai  # type: ignore

        from google.genai import types
        _client = genai.Client(
            api_key=settings.gemini_api_key.strip(),
            http_options=types.HttpOptions(timeout=settings.ai_timeout_ms, retry_options=types.HttpRetryOptions(attempts=1)),
        )
        return _client
    except Exception as exc:  # pragma: no cover - import/config errors
        logger.warning("Gemini client initialization failed (%s)", type(exc).__name__)
        return None


def _generate(prompt: str, system: str | None, json_schema: dict | None, temperature: float, timeout_ms: int | None = None, model: str | None = None, max_output_tokens: int | None = None) -> str:
    from google.genai import types  # type: ignore

    with _client_lock:
        client = _get_client()
    if client is None:
        raise AIError("Gemini is not configured")

    model_name = model or settings.gemini_primary_model
    effective_tokens = max(max_output_tokens or 8192, 4096)
    effective_timeout = timeout_ms or settings.ai_timeout_ms
    config: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": effective_tokens,
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        "automatic_continuation": False,
        "http_options": types.HttpOptions(
            timeout=effective_timeout,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    }
    if hasattr(types, "ThinkingConfig"):
        try:
            budget = getattr(settings, "gemini_thinking_budget", 0)
            config["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
        except Exception:
            pass
    if system:
        config["system_instruction"] = system
    if json_schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_json_schema"] = json_schema

    try:
        response = client.models.generate_content(
            model=model_name, contents=prompt,
            config=types.GenerateContentConfig(**config),
        )
    except Exception as exc:
        if error_code(exc) is not None and error_code(exc)>=400:
            raise  # Preserve real HTTP quota/auth/server errors for failover.
        raise GeminiOutputError("The Gemini SDK could not process the generation response",
                                "SDK_GENERATION_ERROR") from exc
    return extract_gemini_text(response)


class AI:
    """Facade used by routers/services."""

    def __init__(self):
        self._result = ContextVar("ai_result", default=None)

    def _record(self, available: bool, model: str | None = None):
        self._result.set({"state": "available" if available else "unavailable",
                             "model": model or settings.gemini_primary_model,
                             "checked_at": datetime.now(timezone.utc).isoformat()})

    @property
    def status(self) -> dict:
        if not settings.gemini_enabled:
            return {"state": "unconfigured", "model": None, "checked_at": None}
        return self._result.get() or {"state": "not_checked", "model": settings.gemini_primary_model, "checked_at": None}

    @property
    def mode(self) -> str:
        if settings.gemini_enabled and _get_client() is not None:
            return "gemini"
        return "ollama" if settings.enable_local_fallback else "unavailable"

    @property
    def model(self) -> str:
        return settings.gemini_primary_model

    def complete_text(self, prompt, *, system=None, temperature=0.4, fallback=None,
                      timeout_ms=None, model=None, max_output_tokens=None):
        return self._complete(prompt, system, None, temperature, timeout_ms, max_output_tokens)

    def complete_json(self, prompt, schema, *, system=None, temperature=0.3, fallback=None):
        raw, provider = self._complete(prompt, system, schema, temperature, None, None)
        return json.loads(raw), provider

    def _complete(self, prompt, system, schema, temperature, timeout_ms, max_tokens):
        started = time.monotonic()
        failures = []
        last_exc = None
        cloud_exc = None
        cloud_duration = 0.0
        if settings.gemini_enabled:
            cloud_start = time.monotonic()
            raw, model, failures, last_exc = self._try_cloud(
                prompt, system, schema, temperature, timeout_ms, max_tokens)
            cloud_duration = time.monotonic() - cloud_start
            cloud_exc = last_exc
            if raw is not None:
                self._record(True, model)
                logger.info("provider=gemini model=%s success=true latency=%.2fs total_latency=%.2fs",
                            model, cloud_duration, time.monotonic() - started)
                return raw, "gemini"
        if settings.enable_local_fallback:
            ollama_start = time.monotonic()
            try:
                raw = ollama_generate(prompt, system, schema, temperature, max_tokens)
                validate_response(raw, schema)
                self._record(True, settings.ollama_model)
                ollama_duration = time.monotonic() - ollama_start
                total_duration = time.monotonic() - started
                logger.info("provider=ollama model=%s success=true output_validated=true cloud_fallback=%s "
                            "cloud_elapsed=%.2fs ollama_latency=%.2fs total_latency=%.2fs",
                            settings.ollama_model, bool(failures), cloud_duration, ollama_duration, total_duration)
                return raw, "ollama"
            except Exception as exc:
                last_exc = exc
                logger.warning("provider=ollama model=%s success=false error_type=%s code=%s latency=%.2fs",
                               settings.ollama_model, type(exc).__name__, getattr(exc, "code", "provider_output"),
                               time.monotonic() - ollama_start)
                failures.append(f"Ollama: {str(exc) if isinstance(exc, AIError) else type(exc).__name__}")
        self._record(False)
        error = AIError("AI generation unavailable. " + "; ".join(failures or ["No provider configured"]))
        error.diagnostics = getattr(cloud_exc or last_exc, 'ai_diagnostics', {})
        error.cloud_exception = cloud_exc
        if isinstance(last_exc, AIError):
            error.code = last_exc.code
            error.status = last_exc.status
        raise error from last_exc

    def _try_cloud(self, prompt, system, schema, temperature, timeout_ms, max_tokens):
        failures = []
        last_exc = None
        cloud_start = time.monotonic()
        if not quota.cloud_gate.acquire(timeout=max(0, settings.ai_cloud_queue_timeout_seconds)):
            logger.info("provider=gemini decision=ollama reason=admission_timeout wait_time=%.2fs",
                        time.monotonic() - cloud_start)
            return None, None, ['Cloud admission busy'], None
        try:
            effective_timeout = timeout_ms or settings.ai_timeout_ms
            chain = model_chain()
            for idx, model in enumerate(chain):
                cooling = quota.cooldown(model)
                if cooling:
                    info = cooling[1]
                    failures.append(f"{model}: cooldown {info.category}")
                    next_target = "ollama" if info.scope == 'project' or idx + 1 >= len(chain) else chain[idx + 1]
                    logger.info("provider=gemini blocked_model=%s source_model=%s scope=%s category=%s decision=%s cooldown=true",
                                model, info.source_model, info.scope, info.category,
                                'ollama' if info.scope=='project' else next_target)
                    if info.scope == 'project':
                        break
                    continue
                model_start = time.monotonic()
                try:
                    raw = bounded_call(lambda: verified_generate(prompt, system, schema, temperature,
                        effective_timeout, model, max_tokens), model, timeout_ms=effective_timeout)
                    try:
                        validate_response(raw, schema)
                    except (ValueError, jsonschema.ValidationError) as exc:
                        raise GeminiOutputError("Gemini returned invalid structured output", "INVALID_STRUCTURED_OUTPUT") from exc
                    total_cloud_time = time.monotonic() - cloud_start
                    logger.info("provider=gemini model=%s success=true total_cloud_time=%.2fs", model, total_cloud_time)
                    return raw, model, failures, last_exc
                except GeminiOutputError as exc:
                    last_exc = exc
                    exc.ai_diagnostics = {"category": exc.category, "stage": "response_processing", **sanitized_location(exc)}
                    logger.warning("provider=gemini model=%s category=%s stage=response_processing decision=%s diagnostic=%s",
                                   model, exc.category, "next_model" if exc.allow_fallback else "reject", exc.ai_diagnostics)
                    failures.append(f"{model}: {exc.category}")
                    if not exc.allow_fallback:
                        raise
                    continue
                except Exception as exc:
                    last_exc = exc
                    code = error_code(exc)
                    info = quota.classify(exc)
                    exc.ai_diagnostics = {**info.diagnostics(), **sanitized_location(exc)}
                    is_504 = code == 504 or info.category == 'GATEWAY_TIMEOUT'
                    eligible = code in (401, 403, 404, 429, 500, 502, 503, 504) or transient(exc) or info.category == "BILLING_RESTRICTION" or is_504
                    next_target = "ollama" if (info.scope == "project" or code in (401, 403) or idx + 1 >= len(chain)) else chain[idx + 1]
                    logger.warning("provider=gemini model=%s status=%s category=%s scope=%s decision=%s target=%s elapsed=%.2fs diagnostics=%s",
                                   model, code, info.category, info.scope,
                                   "ollama" if (info.scope == "project" or code in (401, 403)) else "next_model",
                                   next_target, time.monotonic() - model_start, exc.ai_diagnostics)
                    failures.append(f"{model}: {info.category if code==429 or info.category in ('BILLING_RESTRICTION', 'GATEWAY_TIMEOUT') else code or type(exc).__name__}")
                    if code == 429 or info.category == 'BILLING_RESTRICTION':
                        quota.exhaust(model, info)
                        if info.scope == 'project':
                            break
                    elif code in (401, 403):
                        quota.exhaust(model, quota.QuotaInfo(category='AUTHENTICATION', scope='project'), 300)
                        if not settings.enable_local_fallback:
                            error = provider_error(exc)
                            error.diagnostics = info.diagnostics()
                            raise error from exc
                        break
                    elif code == 404:
                        quota.exhaust(model, quota.QuotaInfo(category='MODEL_UNAVAILABLE'), 300)
                    elif is_504:
                        quota.exhaust(model, info)
                    elif transient(exc):
                        quota.exhaust(model, quota.QuotaInfo(category='TEMPORARY_FAILURE'), 15)
                    else:
                        error = provider_error(exc)
                        error.diagnostics = info.diagnostics()
                        raise error from exc
            return None, None, failures, last_exc
        finally:
            quota.cloud_gate.release()

    def embed(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[dict[str, float]]:
        """Dense embeddings as sparse {token: weight} dicts keyed by dimension index.

        Raises when Gemini is unavailable so callers fall back to TF-IDF.
        """
        if self.mode != "gemini":
            raise AIError("Gemini is not configured")
        client = _get_client()
        assert client is not None
        from google.genai import types
        if quota.cooldown(settings.gemini_embedding_model):
            raise AIError("Gemini embeddings are cooling down; lexical retrieval remains available")
        try:
            response = client.models.embed_content(
                model=settings.gemini_embedding_model, contents=texts,
                config=types.EmbedContentConfig(task_type=task_type, http_options=types.HttpOptions(
                    timeout=8000, retry_options=types.HttpRetryOptions(attempts=1))),
            )
        except Exception as exc:
            info=quota.classify(exc)
            if error_code(exc)==429 or info.category=='BILLING_RESTRICTION':
                quota.exhaust(settings.gemini_embedding_model, info)
            raise
        vectors: list[dict[str, float]] = []
        for item in response.embeddings:
            vectors.append({str(i): float(v) for i, v in enumerate(item.values)})
        return vectors


def model_chain():
    # Stable deduplication also prevents accidental configuration loops.
    return list(dict.fromkeys(m.strip() for m in [settings.gemini_primary_model,
        settings.gemini_fallback_model_1, settings.gemini_fallback_model_2,
        settings.gemini_fallback_model_3] if m.strip()))


def error_code(exc):
    return quota.status_code(exc)


def transient(exc):
    return error_code(exc) in (500,502,503,504) or isinstance(exc,(httpx.TransportError,TimeoutError,ConnectionError))


def bounded_call(fn, model, timeout_ms=None):
    attempts = max(1, min(settings.ai_retry_attempts, 4))
    consecutive_timeouts = quota.consecutive_timeouts(model)
    # Requirement 3: Avoid retrying the same model repeatedly when it has already returned consecutive 504 errors.
    if consecutive_timeouts >= 1:
        attempts = 1

    model_start = time.monotonic()
    retry_budget = getattr(settings, "ai_model_retry_budget_seconds", 20.0)

    for attempt in range(attempts):
        attempt_start = time.monotonic()
        try:
            result = fn()
            quota.record_success(model)
            return result
        except GeminiOutputError:
            raise  # Invalid output is not a transport error or quota to retry.
        except Exception as exc:
            attempt_duration = time.monotonic() - attempt_start
            total_model_duration = time.monotonic() - model_start
            info = quota.classify(exc)
            exc.ai_diagnostics = info.diagnostics()
            code = error_code(exc)
            is_quota = code == 429 or info.category == 'BILLING_RESTRICTION'
            is_504 = code == 504 or info.category == 'GATEWAY_TIMEOUT'

            if is_quota and (info.category != 'TEMPORARY_CAPACITY' or info.scope == 'project'):
                quota.exhaust(model, info)
                raise

            # For 504 errors: record the timeout in the circuit breaker
            if is_504:
                streak = quota.record_timeout(model)
                logger.warning(
                    "provider=gemini model=%s status=504 category=GATEWAY_TIMEOUT attempt=%d/%d "
                    "attempt_duration=%.2fs total_model_duration=%.2fs consecutive_timeouts=%d",
                    model, attempt + 1, attempts, attempt_duration, total_model_duration, streak
                )
                # If model already has consecutive timeouts (streak > 1), do not retry it; proceed immediately to next model
                if streak > 1:
                    quota.exhaust(model, info)
                    raise

            # Calculate bounded exponential backoff with jitter (Requirements 4 & 5)
            if info.delay is not None:
                delay = info.delay
            else:
                base_delay = min(4.0, 0.5 * (2 ** attempt))
                jitter = random.uniform(0.1, 0.4)
                delay = base_delay + jitter

            # Check retry budget: if retrying would exceed the budget or attempts exhausted, fail over immediately
            if not (transient(exc) or is_quota) or (attempt + 1 >= attempts) or (total_model_duration + delay > retry_budget):
                if is_quota:
                    quota.exhaust(model, info)
                elif is_504:
                    quota.exhaust(model, info)
                elif transient(exc):
                    quota.exhaust(model, quota.QuotaInfo(category="TEMPORARY_FAILURE"), 15)
                raise

            if delay > max(0, settings.ai_max_retry_wait_seconds):
                quota.exhaust(model, info if is_quota else quota.QuotaInfo(
                    category='TEMPORARY_FAILURE', retry_delay=delay), delay)
                raise

            logger.info("provider=gemini model=%s status=%s category=%s retry=%s delay=%.3f total_elapsed=%.2fs",
                        model, code, info.category, attempt + 1, delay, total_model_duration)
            time.sleep(delay)


def verified_generate(prompt, system, schema, temperature, timeout, model, tokens):
    # The actual requested generation is the access test. A model listing is not
    # proof of usable quota, and an extra probe would consume the same scarce quota.
    return _generate(prompt, system, schema, temperature, timeout, model, tokens)


def validate_response(raw, schema):
    if not raw.strip(): raise ValueError("Empty AI response")
    if schema is not None:
        data=json.loads(raw)
        if not isinstance(data,dict): raise ValueError("Expected JSON object")
        jsonschema.validate(data,schema)

def ollama_generate(prompt, system, schema, temperature, tokens):
    messages=[]
    if system: messages.append({"role":"system","content":system})
    messages.append({"role":"user","content":prompt})
    try:
        with httpx.Client(base_url=settings.ollama_base_url,timeout=settings.ai_timeout_ms/1000,trust_env=False) as client:
            tags=client.get("/api/tags", timeout=5); tags.raise_for_status()
            if settings.ollama_model not in {m["name"] for m in tags.json().get("models",[])}:
                raise AIError(f"Model not installed; run ollama pull {settings.ollama_model}")
            payload={"model":settings.ollama_model,"messages":messages,"stream":False,
                     "options":{"temperature":temperature,"num_predict":tokens or 8192,"num_ctx":32768}}
            if schema:
                payload["format"]=schema
                # Qwen3 supports this Ollama-specific control. Structured decoding
                # must reach JSON content within the same finite request budget.
                if settings.ollama_model.rsplit("/",1)[-1].split(":",1)[0]=="qwen3":
                    payload["think"]=settings.ollama_structured_thinking
            response=client.post("/api/chat",json=payload);response.raise_for_status()
            data=response.json()
            if not isinstance(data,dict) or not isinstance(data.get("message"),dict):
                raise AIError("Ollama returned an unexpected response format", "provider_output",502)
            if data.get("done") is False:
                raise AIError("Ollama returned an incomplete generation", "provider_output",502)
            if data.get("done_reason")=="length": raise AIError("Local response truncated", "provider_output",502)
            content=data["message"].get("content", "")
            if isinstance(content, str):
                content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
            if not isinstance(content,str) or not content.strip():raise AIError("Ollama returned no generated text", "provider_output",502)
            return content.strip()
    except httpx.TimeoutException as exc:
        raise AIError("Ollama generation timed out; check local model resources", "provider_timeout",504) from exc
    except httpx.TransportError as exc:
        raise AIError("Cannot connect to local Ollama; start ollama serve") from exc
    except httpx.HTTPStatusError as exc:
        raise AIError(f"Ollama returned HTTP {exc.response.status_code}; check the local service and model") from exc


ai = AI()
