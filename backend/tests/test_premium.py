"""New contract/security tests. Fixture scene responses are not live Gemini evidence."""
from copy import deepcopy
from datetime import datetime,timezone
import time,uuid
import pytest
from pydantic import ValidationError
from tests.test_api import client,auth_headers,_setup
from tests.test_rebuild import material,other
from app.spatial_schema import SceneSpec
from app.database import SessionLocal
from app.models import SpatialEnvironment,SpatialResponse,ReviewLog
API='/api/v1'


def scene_fixture():
    return {'version':1,'title':'How messages move','description':'An authored contract fixture showing an input connected to a processing unit.','objectives':['Trace a message'],'disclaimer':'Authored test specification; not AI-generated.','camera':{'x':8,'y':6,'z':12},'objects':[{'id':'input','label':'Input','type':'box','position':{'x':-2,'y':0,'z':0},'dimensions':{'x':1,'y':1,'z':1},'material':{'color':'#aabbcc'},'explanation':'Input supplies a message to the processor.','source_ids':[]},{'id':'processor','label':'Processor','type':'sphere','position':{'x':2,'y':0,'z':0},'dimensions':{'x':1,'y':1,'z':1},'material':{'color':'#99aa88'},'explanation':'The processor receives the message in this simplified model.','source_ids':[]}],'connections':[{'source':'input','target':'processor','label':'Data path','explanation':'The message travels from the input to the processor.','source_ids':[]}],'steps':[{'title':'Start at the input','explanation':'Select input before following the data path.','object_ids':['input']}],'challenges':[{'id':'find-input','kind':'identify','prompt':'Which component supplies the message?','options':['input','processor'],'answer':['input'],'explanation':'The input supplies the message.','object_ids':['input']}]}

@pytest.mark.parametrize('change',[lambda s:s['objects'][0].update(type='javascript'),lambda s:s['objects'][0]['position'].update(x=100000),lambda s:s['objects'][0]['dimensions'].update(x=-1),lambda s:s['objects'][0].update(script='alert(1)'),lambda s:s['connections'][0].update(target='missing'),lambda s:s['objects'][0].update(animation={'kind':'rotate','duration':100000,'explanation':'Rotate the object'}),lambda s:s['objects'][0]['position'].update(x=float('nan'))])
def test_scene_rejects_unsafe_specs(change):
    data=scene_fixture();change(data)
    with pytest.raises(ValidationError):SceneSpec.model_validate(data)


def test_scene_supports_primitives_and_valid_references():
    scene=SceneSpec.model_validate(scene_fixture())
    assert scene.objects[0].type=='box' and scene.challenges[0].answer==['input']
    bad=scene_fixture();bad['objects']=bad['objects']*30
    with pytest.raises(ValidationError):SceneSpec.model_validate(bad)


def test_spatial_storage_progress_challenges_and_privacy(client,auth_headers,monkeypatch):
    # Isolated generation contract: provider is injected, not claimed as a live service test.
    from app.services import spatial
    from app.routers import spatial as router
    h=other(client)
    monkeypatch.setattr(router,'enqueue_scene',lambda eid:None)
    r=client.post(API+'/spatial',json={'topic':'A previously unsupported message-routing topic'},headers=h)
    assert r.status_code==202,r.text
    eid=r.json()['id']
    monkeypatch.setattr(spatial.ai,'complete_json',lambda *a,**k:(scene_fixture(),'gemini'))
    spatial.generate_scene(eid)
    got=client.get(API+f'/spatial/{eid}',headers=h).json()
    assert got['status']=='ready' and got['scene']['objects'][0]['id']=='input'
    assert 'answer' not in got['scene']['challenges'][0]
    assert client.get(API+f'/spatial/{eid}',headers=auth_headers).status_code==404
    assert client.patch(API+f'/spatial/{eid}',json={'selected':'processor','step':0,'isolated':True},headers=h).status_code==200
    assert client.get(API+f'/spatial/{eid}',headers=h).json()['progress']['selected']=='processor'
    assert client.patch(API+f'/spatial/{eid}',json={'selected':'missing'},headers=h).status_code==422
    body={'challenge_id':'find-input','answer':['input'],'submission_id':uuid.uuid4().hex}
    a=client.post(API+f'/spatial/{eid}/responses',json=body,headers=h).json()
    b=client.post(API+f'/spatial/{eid}/responses',json=body,headers=h).json()
    assert a['correct'] and a['id']==b['id']
    assert len(client.get(API+f'/spatial/{eid}/history',headers=h).json()['responses'])==1
    assert client.delete(API+f'/spatial/{eid}',headers=auth_headers).status_code==404
    assert client.delete(API+f'/spatial/{eid}',headers=h).status_code==204


def test_spatial_invalid_provider_output_fails_persistently(client,auth_headers,monkeypatch):
    from app.services import spatial
    from app.routers import spatial as router
    monkeypatch.setattr(router,'enqueue_scene',lambda eid:None)
    r=client.post(API+'/spatial',json={'topic':'Quantum chemistry'},headers=auth_headers).json()
    data=scene_fixture();data['objects'][0]['position']['x']=999
    monkeypatch.setattr(spatial.ai,'complete_json',lambda *a,**k:(data,'gemini'))
    spatial.generate_scene(r['id'])
    got=client.get(API+f"/spatial/{r['id']}",headers=auth_headers).json()
    assert got['status']=='failed' and got['error'] and 'scene' not in got


def test_revision_complete_workflow_refresh_idempotency_ownership(client,auth_headers):
    h=other(client);lid=material(client,h)
    cards=[]
    for i in range(2):
        c=client.post(API+'/cards',json={'lecture_id':lid,'front':f'Recall question {i}','back':f'Actual source answer {i}'},headers=h)
        assert c.status_code==201;cards.append(c.json())
    overview=client.get(API+'/revision/overview',headers=h).json()
    assert len(overview['due'])==2
    s=client.post(API+'/revision/sessions',json={'limit':20},headers=h).json();sid=s['id']
    assert s['current']['back'] is None
    assert client.get(API+f'/revision/sessions/{sid}',headers=auth_headers).status_code==404
    assert client.get(API+'/revision/sessions/active',headers=h).json()['id']==sid
    for i in range(2):
        current=s['current'];cid=current['id']
        assert client.post(API+f'/revision/sessions/{sid}/rate',json={'card_id':cid,'quality':3},headers=h).status_code==409
        s=client.post(API+f'/revision/sessions/{sid}/reveal',json={'card_id':cid,'answer':'My remembered answer'},headers=h).json()
        assert s['current']['back'] is not None
        assert client.get(API+f'/revision/sessions/{sid}',headers=h).json()['current']['answer']=='My remembered answer'
        s=client.post(API+f'/revision/sessions/{sid}/rate',json={'card_id':cid,'quality':3},headers=h).json()
        repeated=client.post(API+f'/revision/sessions/{sid}/rate',json={'card_id':cid,'quality':3},headers=h).json()
        assert repeated['cursor']==s['cursor']
    assert s['status']=='completed' and len(s['responses'])==2
    for r in s['responses']:assert datetime.fromisoformat(r['next_due'])>datetime.now(timezone.utc)
    assert client.post(API+'/revision/sessions',json={},headers=h).status_code==409
    assert client.get(API+'/revision/overview',headers=h).json()['total']==2


def test_media_validation_rejects_bad_mp4(tmp_path):
    from app.services.video_jobs import validate_mp4
    f=tmp_path/'fake.mp4';f.write_bytes(b'not a movie')
    with pytest.raises(RuntimeError):validate_mp4(f)


def test_missing_ffmpeg_is_a_real_failure(tmp_path,monkeypatch):
    from app.services import video_jobs
    monkeypatch.setattr(video_jobs,'binary',lambda n:None)
    plan={'title':'Test','scenes':[{'type':'title','heading':'Test scene','narration':'This is a real validation test.'}]*2}
    with pytest.raises(RuntimeError,match='FFmpeg'):video_jobs.render_plan(plan,tmp_path)


def test_interrupted_job_recovery(client,auth_headers):
    from app.models import VideoJob,Lecture
    from app.services.video_jobs import recover_jobs
    lid=material(client,auth_headers)
    with SessionLocal() as db:
        l=db.get(Lecture,lid);j=VideoJob(user_id=l.user_id,lecture_id=lid,concept='Interrupted job',status='rendering');db.add(j);db.commit();jid=j.id
    recover_jobs()
    r=client.get(API+f'/video-jobs/{jid}',headers=auth_headers).json()
    assert r['status']=='failed' and 'interrupted' in r['error'].lower()


def test_source_excerpt_branch_reaches_real_renderer(client,auth_headers,monkeypatch):
    from app.models import VideoJob,Lecture
    from app.services import video_jobs
    lid=material(client,auth_headers,body=b'Cells contain genetic information in the nucleus. Ribosomes build proteins from instructions. Mitochondria supply energy to the cell.')
    with SessionLocal() as db:
        lecture=db.get(Lecture,lid);job=VideoJob(user_id=lecture.user_id,lecture_id=lid,concept='Source excerpts',script={'source_excerpt':True},status='queued');db.add(job);db.commit();jid=job.id
    def inspect_renderer(plan,out,update_stage):
        assert len(plan['scenes'])>=2 and out.is_dir()
        assert all(scene['type']=='quote' for scene in plan['scenes'])
        raise RuntimeError('Intentional unit-test renderer boundary')
    monkeypatch.setattr(video_jobs,'render_plan',inspect_renderer)
    video_jobs._run_job(jid)
    with SessionLocal() as db:
        row=db.get(VideoJob,jid)
        assert row.error=='Intentional unit-test renderer boundary' and row.scene_plan['generation_mode']=='source_excerpt'
