"""Quota-aware decisions with realistic Google APIError payloads; no live calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
import json
import httpx
import pytest
from google.genai.errors import APIError
from tests import test_api  # Configure an isolated temporary DB before app imports.
from app.services import ai as gateway
from app.services import ai_quota as quota


def error(kind='RPM',scope='model',delay=None,header=None,code=429,message=None):
    names={'RPM':'GenerateRequestsPerMinute','TPM':'GenerateInputTokensPerMinute','RPD':'GenerateRequestsPerDay'}
    dimensions={'model':'gemini-2.5-flash','location':'global'} if scope=='model' else {'project':'PRIVATE_PROJECT'}
    details=[]
    if kind in names:
        details.append({'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[{
            'quotaMetric':'generativelanguage.googleapis.com/generate_content_requests',
            'quotaId':names[kind]+'PerProject'+('PerModel' if scope=='model' else ''),
            'quotaDimensions':dimensions}]})
    if delay is not None:details.append({'@type':'type.googleapis.com/google.rpc.RetryInfo','retryDelay':delay})
    if message is None:message={'BILLING':'Billing spend restriction','CAPACITY':'Temporary model capacity throttling'}.get(kind,'Quota exceeded')
    response=httpx.Response(code,headers={'Retry-After':str(header)} if header is not None else {})
    return APIError(code,{'error':{'code':code,'message':message,'status':'RESOURCE_EXHAUSTED','details':details}},response)


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    quota.clear()
    monkeypatch.setattr(gateway.settings,'gemini_api_key','unit-test-only')
    monkeypatch.setattr(gateway.settings,'ai_retry_attempts',2)
    monkeypatch.setattr(gateway.settings,'ai_max_retry_wait_seconds',10)
    monkeypatch.setattr(gateway.settings,'enable_local_fallback',True)
    monkeypatch.setattr(gateway.settings,'gemini_primary_model','gemini-2.5-flash')
    monkeypatch.setattr(gateway.settings,'gemini_fallback_model_1','gemini-3.8-flash')
    monkeypatch.setattr(gateway.settings,'gemini_fallback_model_2','gemini-3.7-flash')
    monkeypatch.setattr(gateway.settings,'gemini_fallback_model_3','gemini-3.6-flash')
    yield
    quota.clear()


def test_exact_priority_and_primary_success(monkeypatch):
    fn=Mock(return_value='actual provider response');monkeypatch.setattr(gateway,'verified_generate',fn)
    assert gateway.model_chain()==['gemini-2.5-flash','gemini-3.8-flash','gemini-3.7-flash','gemini-3.6-flash']
    assert gateway.AI().complete_text('question')==('actual provider response','gemini')
    assert fn.call_args.args[5]=='gemini-2.5-flash'


@pytest.mark.parametrize('kind',['RPM','TPM','RPD','UNKNOWN'])
def test_model_quota_immediately_advances_and_cools(monkeypatch,kind):
    fn=Mock(side_effect=[error(kind),'next response','another response'])
    monkeypatch.setattr(gateway,'verified_generate',fn)
    sleep=Mock();monkeypatch.setattr(gateway.time,'sleep',sleep)
    ai=gateway.AI()
    assert ai.complete_text('x')==('next response','gemini')
    assert fn.call_args.args[5]=='gemini-3.8-flash'
    ai.complete_text('x')
    assert [c.args[5] for c in fn.call_args_list]==['gemini-2.5-flash','gemini-3.8-flash','gemini-3.8-flash']
    sleep.assert_not_called()
    if kind=='RPD':assert quota.cooldown('gemini-2.5-flash')[0]-quota.time.monotonic()>60


@pytest.mark.parametrize('kind',['RPM','TPM','RPD','BILLING'])
def test_project_quota_goes_directly_local(monkeypatch,kind):
    fn=Mock(side_effect=error(kind,scope='project'));monkeypatch.setattr(gateway,'verified_generate',fn)
    local=Mock(return_value='local response');monkeypatch.setattr(gateway,'ollama_generate',local)
    for _ in range(2):assert gateway.AI().complete_text('x')==('local response','ollama')
    assert fn.call_count==1
    assert local.call_count==2


def test_billing_403_goes_local(monkeypatch):
    fn=Mock(side_effect=error('BILLING',code=403));monkeypatch.setattr(gateway,'verified_generate',fn)
    monkeypatch.setattr(gateway,'ollama_generate',lambda *a:'local')
    assert gateway.AI().complete_text('x')[1]=='ollama';assert fn.call_count==1


def test_capacity_respects_longest_delay(monkeypatch):
    fn=Mock(side_effect=[error('CAPACITY',delay='2.25s',header=3),'ok'])
    monkeypatch.setattr(gateway,'verified_generate',fn)
    sleep=Mock();monkeypatch.setattr(gateway.time,'sleep',sleep)
    assert gateway.AI().complete_text('x')==('ok','gemini')
    sleep.assert_called_once_with(3)


def test_long_delay_defers_without_sleep(monkeypatch):
    fn=Mock(side_effect=[error('CAPACITY',delay='120s'),'ok']);monkeypatch.setattr(gateway,'verified_generate',fn)
    sleep=Mock();monkeypatch.setattr(gateway.time,'sleep',sleep)
    assert gateway.AI().complete_text('x')==('ok','gemini')
    assert quota.cooldown('gemini-2.5-flash')[0]-quota.time.monotonic()>119
    sleep.assert_not_called()


def test_retry_after_formats():
    now=datetime(2026,11,15,tzinfo=timezone.utc)
    assert quota.retry_after('15',now)==15
    assert quota.retry_after('Sun, 15 Nov 2026 00:00:12 GMT',now)==12
    assert quota.retry_after('nonsense',now) is None
    assert quota.retry_after('NaN',now) is None
    assert quota.seconds({'seconds':'2','nanos':500000000})==2.5


def test_unknown_retains_only_safe_metadata():
    exc=error('UNKNOWN',delay='17s',message='PRIVATE_PROMPT SECRET_API_KEY')
    info=quota.classify(exc)
    assert info.category=='UNKNOWN_QUOTA_LIMIT'
    assert info.delay==17
    assert 'PRIVATE_PROMPT' not in json.dumps(info.diagnostics())
    assert 'PRIVATE_PROJECT' not in json.dumps(quota.classify(error(scope='project')).diagnostics())


def test_multiple_violations_shared_wins():
    exc=error('RPM');other=error('TPM',scope='project')
    exc.details['error']['details']+=other.details['error']['details']
    info=quota.classify(exc)
    assert info.category=='TPM' and info.scope=='project'


def test_cooldown_expires(monkeypatch):
    clock=Mock(return_value=100);monkeypatch.setattr(quota.time,'monotonic',clock)
    quota.exhaust('model',quota.QuotaInfo(category='RPM'),2)
    assert quota.cooldown('model')
    clock.return_value=103
    assert quota.cooldown('model') is None


def test_concurrent_quota_only_one_cloud_attempt(monkeypatch):
    fn=Mock(side_effect=error('TPM',scope='project'));monkeypatch.setattr(gateway,'verified_generate',fn)
    monkeypatch.setattr(gateway,'ollama_generate',lambda *a:'local')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:gateway.AI().complete_text('x'),range(20)))
    assert all(x==('local','ollama') for x in results)
    assert fn.call_count==1


def test_context_schema_preserved_on_cloud_failure(monkeypatch):
    fn=Mock(side_effect=error('TPM',scope='project'));monkeypatch.setattr(gateway,'verified_generate',fn)
    local=Mock(return_value='{"answer":"valid"}');monkeypatch.setattr(gateway,'ollama_generate',local)
    prompt='Conversation history: prior question. Lecture: cells. Uploaded document: ATP.'
    schema={'type':'object','required':['answer'],'properties':{'answer':{'type':'string'}}}
    assert gateway.AI().complete_json(prompt,schema,system='source grounded')[0]=={'answer':'valid'}
    assert fn.call_args.args[:3]==local.call_args.args[:3]==(prompt,'source grounded',schema)


def test_unavailable_error_retains_cloud_cause(monkeypatch):
    original=error('BILLING');monkeypatch.setattr(gateway,'verified_generate',Mock(side_effect=original))
    monkeypatch.setattr(gateway,'ollama_generate',Mock(side_effect=gateway.AIError('Local unavailable')))
    with pytest.raises(gateway.AIError) as caught:gateway.AI().complete_text('x')
    assert caught.value.cloud_exception is original
    assert caught.value.diagnostics['category']=='BILLING_RESTRICTION'
    assert 'PRIVATE_PROJECT' not in str(caught.value)


def test_no_quota_log_leaks(monkeypatch,caplog):
    monkeypatch.setattr(gateway,'verified_generate',Mock(side_effect=error('UNKNOWN',message='SECRET_API_KEY PRIVATE_LECTURE')))
    monkeypatch.setattr(gateway,'ollama_generate',lambda *a:'safe')
    gateway.AI().complete_text('PRIVATE_CONVERSATION')
    assert not any(x in caplog.text for x in ['SECRET_API_KEY','PRIVATE_LECTURE','PRIVATE_CONVERSATION'])


def test_errorinfo_metadata_classifies_shared_tpm():
    exc=APIError(429,{'error':{'status':'RESOURCE_EXHAUSTED','message':'Rate limit', 'details':[{
        '@type':'type.googleapis.com/google.rpc.ErrorInfo','reason':'RATE_LIMIT_EXCEEDED',
        'metadata':{'quota_metric':'generativelanguage.googleapis.com/input_tokens',
                    'quota_limit':'GenerateInputTokensPerMinutePerProject','consumer':'PRIVATE_PROJECT'}}]}})
    info=quota.classify(exc)
    assert info.category=='TPM' and info.scope=='project'
    assert 'PRIVATE_PROJECT' not in json.dumps(info.diagnostics())


def test_http_response_json_supported():
    payload=error('RPM').details
    response=httpx.Response(429,json=payload,request=httpx.Request('POST','https://example.test'))
    exc=httpx.HTTPStatusError('failure',request=response.request,response=response)
    assert quota.classify(exc).category=='RPM'


def test_embedding_honors_project_cooldown(monkeypatch):
    client=Mock();monkeypatch.setattr(gateway,'_get_client',lambda:client)
    quota.exhaust('other-model',quota.QuotaInfo(category='TPM',scope='project'))
    with pytest.raises(gateway.AIError,match='cooling down'):gateway.AI().embed(['private source'])
    client.models.embed_content.assert_not_called()


def test_admin_check_honors_shared_quota(monkeypatch):
    from app.routers.ai_preview import provider_check
    fn=Mock(side_effect=error('TPM',scope='project'));monkeypatch.setattr(gateway,'verified_generate',fn)
    result=provider_check(user=None)
    assert not result['connected']
    assert fn.call_count==1
    assert all(x.get('cooldown') for x in result['models'][1:])


def test_qwen_structured_thinking_is_provider_specific(monkeypatch):
    response=Mock();response.json.return_value={'message':{'content':'{"ok":true}'}}
    tags=Mock();tags.json.return_value={'models':[{'name':'qwen3:4b'}]}
    client=Mock();client.get.return_value=tags;client.post.return_value=response
    context=Mock();context.__enter__=Mock(return_value=client);context.__exit__=Mock(return_value=False)
    monkeypatch.setattr(gateway.httpx,'Client',lambda **kw:context)
    monkeypatch.setattr(gateway.settings,'ollama_structured_thinking',False)
    schema={'type':'object'}
    gateway.ollama_generate('prompt','system',schema,.3,None)
    payload=client.post.call_args.kwargs['json']
    assert payload['think'] is False and payload['format']==schema
    assert payload['messages']==[{'role':'system','content':'system'},{'role':'user','content':'prompt'}]
    gateway.ollama_generate('prompt','system',None,.3,None)
    assert 'think' not in client.post.call_args.kwargs['json']
