"""Deterministic provider failures and controlled media validation."""
import json
from unittest.mock import Mock
import pytest
import httpx
from tests import test_api  # Initialize the suite's temporary database before app imports.
from app.services import ai as gateway
from app.services.ai import AI,AIError

@pytest.fixture(autouse=True)
def config(monkeypatch):
    gateway.quota.clear()
    monkeypatch.setattr(gateway.settings,'gemini_api_key','test-only')
    monkeypatch.setattr(gateway.ai,'_record',lambda *a:None)
    monkeypatch.setattr(gateway.settings,'ai_retry_attempts',2)
    monkeypatch.setattr(gateway.time,'sleep',lambda _:None)
    yield
    gateway.quota.clear()

def failure(code):
    e=RuntimeError('private provider content must not escape');e.code=code;return e

@pytest.mark.parametrize('failures,expected',[(0,0),(2,1),(4,2),(6,None)])
def test_priority(monkeypatch,failures,expected):
    fn=Mock(side_effect=[failure(503)]*failures+['valid'])
    monkeypatch.setattr(gateway,'verified_generate',fn)
    local=Mock(return_value='local');monkeypatch.setattr(gateway,'ollama_generate',local)
    text,mode=AI().complete_text('history lecture documents',system='rules')
    assert mode==('ollama' if expected is None else 'gemini')
    if expected is not None:assert fn.call_args.args[5]==gateway.model_chain()[expected]
    else:assert local.call_args.args[:2]==('history lecture documents','rules')

@pytest.mark.parametrize('code',[400,401,403])
def test_permanent_no_retry(monkeypatch,code):
    fn=Mock(side_effect=failure(code));monkeypatch.setattr(gateway,'verified_generate',fn)
    with pytest.raises(AIError):AI().complete_text('x')
    assert fn.call_count==1

@pytest.mark.parametrize('exc',[failure(503),httpx.ReadTimeout('timeout')])
def test_retry_then_success(monkeypatch,exc):
    fn=Mock(side_effect=[exc,'ok']);monkeypatch.setattr(gateway,'verified_generate',fn)
    assert AI().complete_text('x')==('ok','gemini');assert fn.call_count==2

def test_model_unavailable_skips(monkeypatch):
    fn=Mock(side_effect=[failure(404),'ok']);monkeypatch.setattr(gateway,'verified_generate',fn)
    assert AI().complete_text('x')[0]=='ok';assert fn.call_count==2

def test_bad_local_output(monkeypatch):
    monkeypatch.setattr(gateway.settings,'gemini_api_key','')
    monkeypatch.setattr(gateway,'ollama_generate',lambda *a:'{"count":"wrong"}')
    with pytest.raises(AIError):AI().complete_json('x',{'type':'object','properties':{'count':{'type':'integer'}},'required':['count']})

def test_local_unavailable(monkeypatch):
    monkeypatch.setattr(gateway.settings,'gemini_api_key','')
    monkeypatch.setattr(gateway,'ollama_generate',Mock(side_effect=AIError('start ollama serve')))
    with pytest.raises(AIError,match='start ollama serve'):AI().complete_text('x')

def test_local_schema_context(monkeypatch):
    monkeypatch.setattr(gateway.settings,'gemini_api_key','')
    fn=Mock(return_value='{"ok":true}');monkeypatch.setattr(gateway,'ollama_generate',fn)
    schema={'type':'object','required':['ok'],'properties':{'ok':{'type':'boolean'}}}
    assert AI().complete_json('history\nlecture\ndocument',schema,system='rules')==({'ok':True},'ollama')
    assert fn.call_args.args[:3]==('history\nlecture\ndocument','rules',schema)

def test_missing_model(monkeypatch):
    response=Mock();response.json.return_value={'models':[]}
    client=Mock();client.get.return_value=response
    ctx=Mock();ctx.__enter__=Mock(return_value=client);ctx.__exit__=Mock(return_value=False)
    monkeypatch.setattr(gateway.httpx,'Client',Mock(return_value=ctx))
    with pytest.raises(AIError,match='ollama pull'):gateway.ollama_generate('x',None,None,.3,None)
