"""Real SDK response types and deterministic post-HTTP response regressions."""
from types import SimpleNamespace
from unittest.mock import Mock
import logging
import pytest
from google.genai import types
from tests.test_api import client,auth_headers,_setup
from app.services import ai as gateway
from app.services import ai_quota as quota

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    quota.clear()
    monkeypatch.setattr(gateway.settings,'gemini_api_key','unit-test-only')
    monkeypatch.setattr(gateway.settings,'gemini_primary_model','gemini-3.6-flash')
    monkeypatch.setattr(gateway.settings,'gemini_fallback_model_1','gemini-3.7-flash')
    monkeypatch.setattr(gateway.settings,'gemini_fallback_model_2','gemini-3.8-flash')
    monkeypatch.setattr(gateway.settings,'gemini_fallback_model_3','')
    yield
    quota.clear()


def candidate(parts,reason='STOP'):
    return types.Candidate(content=types.Content(role='model',parts=parts),finish_reason=reason)


def response(parts,reason='STOP'):
    return types.GenerateContentResponse(candidates=[candidate(parts,reason)])


def test_real_sdk_text_parts_skip_thoughts():
    r=response([types.Part(text='PRIVATE_THOUGHT',thought=True),types.Part(text='Actual '),types.Part(text='answer')])
    assert gateway.extract_gemini_text(r)=='Actual answer'


def test_sdk_text_property_is_never_accessed():
    class BrokenConvenience:
        candidates=[candidate([types.Part(text='Valid SDK parts')])]
        @property
        def text(self):raise RuntimeError('SDK convenience serialization failed PRIVATE_CONTENT')
    assert gateway.extract_gemini_text(BrokenConvenience())=='Valid SDK parts'


def test_raw_mapping_parts():
    assert gateway.extract_gemini_text({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'Valid'}]}}]})=='Valid'


def test_valid_alternative_candidate():
    r=types.GenerateContentResponse(candidates=[candidate([], 'MAX_TOKENS'),candidate([types.Part(text='Complete answer')])])
    assert gateway.extract_gemini_text(r)=='Complete answer'


def test_function_only_is_not_an_answer_or_executed(caplog):
    caplog.set_level(logging.INFO,logger="oraya.ai")
    r=response([types.Part(function_call=types.FunctionCall(name='PRIVATE_TOOL',args={'private':'PRIVATE_ARGUMENT'}))])
    with pytest.raises(gateway.GeminiOutputError) as caught:gateway.extract_gemini_text(r)
    assert caught.value.category=='UNEXPECTED_FUNCTION_CALL'
    assert caught.value.code=='provider_output'
    assert 'PRIVATE_TOOL' not in caplog.text and 'PRIVATE_ARGUMENT' not in caplog.text


def test_valid_text_with_unexecuted_nontext_part():
    r=response([types.Part(text='Valid answer'),types.Part(function_call=types.FunctionCall(name='unused'))])
    assert gateway.extract_gemini_text(r)=='Valid answer'


@pytest.mark.parametrize('r',[types.GenerateContentResponse(),types.GenerateContentResponse(candidates=[types.Candidate()]),response([]),response([types.Part(text='  ')]),response([types.Part(text='thinking only',thought=True)])])
def test_empty_output_is_typed(r):
    with pytest.raises(gateway.GeminiOutputError) as caught:gateway.extract_gemini_text(r)
    assert caught.value.category=='EMPTY_RESPONSE' and caught.value.status==502


@pytest.mark.parametrize('r',[
    response([types.Part(text='blocked content')],'SAFETY'),
    types.GenerateContentResponse(prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason='SAFETY')),
    types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[types.Part(text='blocked')]),finish_reason='STOP',safety_ratings=[types.SafetyRating(blocked=True)])])])
def test_safety_block_rejected(r):
    with pytest.raises(gateway.GeminiOutputError) as caught:gateway.extract_gemini_text(r)
    assert caught.value.category=='SAFETY_BLOCK' and not caught.value.allow_fallback


def test_truncated_output_rejected():
    with pytest.raises(gateway.GeminiOutputError) as caught:gateway.extract_gemini_text(response([types.Part(text='partial')],'MAX_TOKENS'))
    assert caught.value.category=='OUTPUT_TRUNCATED'


def test_sdk_structure_failure_has_original_cause():
    class BrokenResponse:
        @property
        def candidates(self):raise TypeError('PRIVATE_RESPONSE_BODY')
    with pytest.raises(gateway.GeminiOutputError) as caught:gateway.extract_gemini_text(BrokenResponse())
    assert caught.value.category=='SDK_RESPONSE_PARSE_ERROR'
    assert isinstance(caught.value.__cause__,TypeError)
    assert gateway.sanitized_location(caught.value)['exception_class']=='TypeError'


def test_afc_disabled_and_valid_primary_never_falls_back(monkeypatch):
    fn=Mock(return_value=response([types.Part(text='Actual answer')]))
    client=SimpleNamespace(models=SimpleNamespace(generate_content=fn))
    monkeypatch.setattr(gateway,'_get_client',lambda:client)
    local=Mock(side_effect=AssertionError('No local call'));monkeypatch.setattr(gateway,'ollama_generate',local)
    assert gateway.AI().complete_text('private prompt')==('Actual answer','gemini')
    assert fn.call_count==1
    assert fn.call_args.kwargs['model']=='gemini-3.6-flash'
    assert fn.call_args.kwargs['config'].automatic_function_calling.disable is True
    local.assert_not_called()


def test_parse_error_reports_class_location_and_uses_next_model(monkeypatch,caplog):
    class BrokenResponse:
        @property
        def candidates(self):raise AttributeError('PRIVATE_CONTENT API_KEY')
    fn=Mock(side_effect=[BrokenResponse(),response([types.Part(text='secondary')])])
    monkeypatch.setattr(gateway,'_get_client',lambda:SimpleNamespace(models=SimpleNamespace(generate_content=fn)))
    caplog.set_level(logging.INFO,logger='oraya.ai')
    assert gateway.AI().complete_text('PRIVATE_PROMPT')==('secondary','gemini')
    assert "'exception_class': 'AttributeError'" in caplog.text
    assert 'test_gemini_response_parsing.py:' in caplog.text
    assert 'SDK_RESPONSE_PARSE_ERROR' in caplog.text
    assert all(secret not in caplog.text for secret in ['PRIVATE_CONTENT','API_KEY','PRIVATE_PROMPT'])
    assert 'BILLING_RESTRICTION' not in caplog.text and 'MODEL_UNAVAILABLE' not in caplog.text
    assert not quota.cooldown('gemini-3.6-flash')


def test_sdk_generation_parsing_failure_is_typed(monkeypatch):
    fn=Mock(side_effect=ValueError('PRIVATE_BODY'))
    monkeypatch.setattr(gateway,'_get_client',lambda:SimpleNamespace(models=SimpleNamespace(generate_content=fn)))
    with pytest.raises(gateway.GeminiOutputError) as caught:gateway._generate('question',None,None,.3)
    assert caught.value.category=='SDK_GENERATION_ERROR' and isinstance(caught.value.__cause__,ValueError)


def test_authenticated_tutor_receives_sdk_candidate_text(client,auth_headers,monkeypatch):
    monkeypatch.setattr(gateway.settings,'allow_demo_ai',False)
    fn=Mock(return_value=response([types.Part(text="Newton's second law says force equals mass times acceleration [1:00].")]))
    monkeypatch.setattr(gateway,'_get_client',lambda:SimpleNamespace(models=SimpleNamespace(generate_content=fn)))
    from app.database import SessionLocal
    from app.models import Lecture, TranscriptSegment
    import uuid
    user=client.get('/api/v1/auth/me',headers=auth_headers).json()
    with SessionLocal() as db:
        lecture=Lecture(user_id=user['id'],video_id=uuid.uuid4().hex[:20],url='https://example.test/lesson',
                        title='Newton lesson',source='upload',transcript_status='ready')
        db.add(lecture);db.flush();lid=lecture.id
        db.add(TranscriptSegment(lecture_id=lid,idx=0,start=60,end=90,
               text="Newton's second law says force equals mass times acceleration."))
        db.commit()
    answer="Newton's second law relates force, mass and acceleration [1:00]."
    fn.return_value=response([types.Part(text=answer)])
    try:
        r=client.post(f'/api/v1/lectures/{lid}/tutor/ask',headers=auth_headers,json={'question':"What does Newton's second law say?"})
        assert r.status_code==200,r.text
        assert r.json()['mode']=='gemini' and r.json()['answer']==answer
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Lecture,lid));db.commit()



def test_http_200_sdk_failure_is_never_quota_or_model_error(monkeypatch,caplog):
    from google.genai.errors import APIError
    exc=APIError(200,{'error':{'message':'PRIVATE_BODY billing model not found'}})
    fn=Mock(side_effect=[exc,response([types.Part(text='complete')])])
    monkeypatch.setattr(gateway,'_get_client',lambda:SimpleNamespace(models=SimpleNamespace(generate_content=fn)))
    assert gateway.AI().complete_text('x')==('complete','gemini')
    assert 'SDK_GENERATION_ERROR' in caplog.text
    assert 'BILLING_RESTRICTION' not in caplog.text and 'MODEL_UNAVAILABLE' not in caplog.text
    assert 'PRIVATE_BODY' not in caplog.text
    assert not quota.cooldown('gemini-3.6-flash')
