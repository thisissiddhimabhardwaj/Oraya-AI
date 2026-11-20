"""Regressions for the actual generation 404, model-specific daily 429 and state logs."""
from unittest.mock import Mock
import pytest
from tests.test_ai_quota import error, isolated
from app.services import ai as gateway
from app.services import ai_quota as quota
from google.genai.errors import APIError


def daily():
    exc=error('RPD',delay='8570s',message='You exceeded your current quota, please check your plan and billing details. For more information, see billing documentation.')
    v=exc.details['error']['details'][0]['violations'][0]
    v.update(quotaId='GenerateRequestsPerDayPerProjectPerModel-FreeTier',quotaValue='20',quotaDimensions={'model':'gemini-3.8-flash','location':'global'})
    return exc


def test_actual_daily_metadata_is_not_billing():
    info=quota.classify(daily())
    assert info.category=='DAILY_QUOTA_EXHAUSTED' and info.scope=='model'
    assert info.delay==8570
    assert info.metrics[0]['quota_value']=='20'


def test_daily_uses_explicit_delay_not_assumed_reset(monkeypatch):
    monkeypatch.setattr(quota.time,'monotonic',lambda:100)
    quota.exhaust('gemini-3.8-flash',quota.classify(daily()))
    assert quota.cooldown('gemini-3.8-flash')[0]==8670
    assert quota.cooldown('gemini-2.5-flash') is None
    assert quota.cooldown('gemini-3.7-flash') is None


def test_404_never_billing_even_with_guidance():
    info=quota.classify(error('BILLING',code=404,message='Model not found. Check billing restrictions.'))
    assert info.category=='MODEL_UNAVAILABLE' and info.scope=='model'


def test_independent_models_skip_404_and_daily_then_local(monkeypatch):
    fn=Mock(side_effect=[error('UNKNOWN',code=404),daily(),error('UNKNOWN',code=404),error('UNKNOWN',code=404)])
    monkeypatch.setattr(gateway,'verified_generate',fn)
    local=Mock(return_value='Generated local answer');monkeypatch.setattr(gateway,'ollama_generate',local)
    for _ in range(2):assert gateway.AI().complete_text('history lecture transcript document',system='rules')==('Generated local answer','ollama')
    assert fn.call_count==4
    assert quota.cooldown('gemini-2.5-flash')[1].category=='MODEL_UNAVAILABLE'
    assert quota.cooldown('gemini-3.8-flash')[1].category=='DAILY_QUOTA_EXHAUSTED'
    assert local.call_args.args[:2]==('history lecture transcript document','rules')


def test_shared_cooldown_logs_origin_not_current_model(monkeypatch,caplog):
    import logging
    caplog.set_level(logging.INFO,logger='oraya.ai')
    quota.exhaust('gemini-3.8-flash',quota.QuotaInfo(category='BILLING_RESTRICTION',scope='project'))
    monkeypatch.setattr(gateway,'verified_generate',Mock(side_effect=AssertionError('must skip')))
    monkeypatch.setattr(gateway,'ollama_generate',lambda *a:'valid')
    gateway.AI().complete_text('x')
    assert 'source_model=gemini-3.8-flash scope=project category=BILLING_RESTRICTION' in caplog.text
    assert 'provider=gemini model=gemini-2.5-flash category=BILLING_RESTRICTION' not in caplog.text


def test_per_model_quotas_keep_separate_identities(monkeypatch):
    first=quota.classify(error('RPM'))
    second=quota.classify(daily())
    quota.exhaust('model',first)
    quota.exhaust('model',second)
    assert len(quota._cooldowns)==2
    assert quota.cooldown('model')[1].category=='DAILY_QUOTA_EXHAUSTED'


def test_503_respects_retryinfo(monkeypatch):
    fn=Mock(side_effect=[error('CAPACITY',code=503,delay='4s'),'valid'])
    monkeypatch.setattr(gateway,'verified_generate',fn)
    sleep=Mock();monkeypatch.setattr(gateway.time,'sleep',sleep)
    assert gateway.AI().complete_text('x')==('valid','gemini')
    sleep.assert_called_once_with(4)


def test_ollama_http_200_empty_and_truncated_not_success(monkeypatch):
    tags=Mock();tags.json.return_value={'models':[{'name':'qwen3:4b'}]}
    response=Mock()
    client=Mock();client.get.return_value=tags;client.post.return_value=response
    ctx=Mock();ctx.__enter__=Mock(return_value=client);ctx.__exit__=Mock(return_value=False)
    monkeypatch.setattr(gateway.httpx,'Client',lambda **kw:ctx)
    for payload in [None, [], {'message':None}, {'message':{'content':'partial'},'done':False}, {'message':{'content':''}},{'message':{'content':'partial'},'done_reason':'length'}]:
        response.json.return_value=payload
        with pytest.raises(gateway.AIError):gateway.ollama_generate('history lecture','rules',None,.3,800)


def test_explicit_billing_reason_is_distinct_from_generic_guidance():
    exc=daily()
    exc.details['error']['details'].append({'@type':'type.googleapis.com/google.rpc.ErrorInfo','reason':'BILLING_DISABLED'})
    info=quota.classify(exc)
    assert info.category=='BILLING_RESTRICTION' and info.scope=='project'
