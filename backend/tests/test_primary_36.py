"""Current priority and migration regressions; no live network or production DB."""
from unittest.mock import Mock
import pytest
from google.genai.errors import APIError
from tests import test_api
from app.config import Settings
from app.services import ai as gateway
from app.services import ai_quota as quota

FIELDS=['gemini_model','gemini_tutor_model','gemini_primary_model','gemini_fallback_model_1','gemini_fallback_model_2','gemini_fallback_model_3']

@pytest.fixture(autouse=True)
def current(monkeypatch):
    for field in FIELDS:monkeypatch.delenv(field.upper(),raising=False)
    defaults=Settings(_env_file=None)
    for field in FIELDS:monkeypatch.setattr(gateway.settings,field,getattr(defaults,field))
    monkeypatch.setattr(gateway.settings,'gemini_api_key','unit-test-only')
    monkeypatch.setattr(gateway.settings,'enable_local_fallback',True)
    monkeypatch.setattr(gateway.settings,'ai_retry_attempts',1)
    quota.clear()
    yield
    quota.clear()


def unavailable():
    return APIError(404,{'error':{'status':'NOT_FOUND','message':'Model unavailable'}})


def test_new_defaults():
    assert gateway.model_chain()==['gemini-3.8-flash','gemini-3.7-flash','gemini-3.6-flash']
    assert gateway.settings.gemini_model==gateway.settings.gemini_tutor_model==gateway.ai.model=='gemini-3.8-flash'


def test_exact_old_env_chain_migrated_without_replacing_credentials():
    config=Settings(_env_file=None,gemini_api_key='keep-test-key',gemini_model='gemini-2.5-flash',gemini_tutor_model='gemini-2.5-flash',gemini_primary_model='gemini-2.5-flash',gemini_fallback_model_1='gemini-3.8-flash',gemini_fallback_model_2='gemini-3.7-flash',gemini_fallback_model_3='gemini-3.6-flash')
    assert config.gemini_api_key=='keep-test-key'
    assert (config.gemini_primary_model,config.gemini_fallback_model_1,config.gemini_fallback_model_2,config.gemini_fallback_model_3)==('gemini-3.8-flash','gemini-3.7-flash','gemini-3.6-flash','')
    assert config.gemini_model==config.gemini_tutor_model=='gemini-3.8-flash'


def test_explicit_custom_chain_remains_configurable():
    config=Settings(_env_file=None,gemini_primary_model='custom-model')
    assert config.gemini_primary_model=='custom-model'


def test_tutor_call_cannot_bypass_shared_priority(monkeypatch):
    fn=Mock(return_value='Generated answer');monkeypatch.setattr(gateway,'verified_generate',fn)
    assert gateway.AI().complete_text('lecture history',model='gemini-2.5-flash')==('Generated answer','gemini')
    assert fn.call_args.args[5]=='gemini-3.8-flash'


def test_primary_404_moves_to_secondary_and_stays_cooled(monkeypatch):
    fn=Mock(side_effect=[unavailable(),'secondary','secondary again']);monkeypatch.setattr(gateway,'verified_generate',fn)
    gateway.AI().complete_text('x');gateway.AI().complete_text('x')
    assert [c.args[5] for c in fn.call_args_list]==['gemini-3.8-flash','gemini-3.7-flash','gemini-3.7-flash']


def test_primary_quota_moves_to_secondary(monkeypatch):
    exc=APIError(429,{'error':{'status':'RESOURCE_EXHAUSTED','details':[{'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[{'quotaId':'GenerateRequestsPerDayPerProjectPerModel','quotaDimensions':{'model':'gemini-3.8-flash'}}]}]}})
    fn=Mock(side_effect=[exc,'secondary']);monkeypatch.setattr(gateway,'verified_generate',fn)
    assert gateway.AI().complete_text('x')==('secondary','gemini')
    assert fn.call_args.args[5]=='gemini-3.7-flash'
    assert quota.cooldown('gemini-3.8-flash') and not quota.cooldown('gemini-3.7-flash')


def test_tertiary_quota_does_not_block_primary(monkeypatch):
    quota.exhaust('gemini-3.6-flash',quota.QuotaInfo(category='DAILY_QUOTA_EXHAUSTED',retry_delay=8570))
    fn=Mock(return_value='primary');monkeypatch.setattr(gateway,'verified_generate',fn)
    assert gateway.AI().complete_text('x')==('primary','gemini')
    assert fn.call_args.args[5]=='gemini-3.8-flash'


def test_all_cloud_unavailable_then_ollama_preserves_context(monkeypatch):
    fn=Mock(side_effect=unavailable());monkeypatch.setattr(gateway,'verified_generate',fn)
    local=Mock(return_value='local');monkeypatch.setattr(gateway,'ollama_generate',local)
    assert gateway.AI().complete_text('history lecture document',system='rules')==('local','ollama')
    assert [c.args[5] for c in fn.call_args_list]==gateway.model_chain()
    assert local.call_args.args[:2]==('history lecture document','rules')


def test_structured_generation_starts_at_primary(monkeypatch):
    fn=Mock(return_value='{"answer":"valid"}');monkeypatch.setattr(gateway,'verified_generate',fn)
    assert gateway.AI().complete_json('script',{'type':'object','required':['answer']})==({'answer':'valid'},'gemini')
    assert fn.call_args.args[5]=='gemini-3.8-flash'
