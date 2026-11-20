"""Integration regressions for the independent rebuild using real temporary SQLite records."""
from datetime import datetime,timedelta,timezone
import pytest
from tests.test_api import client,auth_headers,_setup
from app.database import SessionLocal
from app.models import Lecture,Quiz,QuizQuestion,ExamSession
API='/api/v1'


def other(client):
    import uuid
    r=client.post(API+'/auth/signup',json={'name':'Other student','email':f'{uuid.uuid4().hex}@example.com','password':'another123'})
    return {'Authorization':'Bearer '+r.json()['access_token']}


def material(client,h,name='biology.txt',body=b'Cells contain a nucleus. Mitochondria produce ATP. Cells have a membrane. Proteins are made at ribosomes.'):
    r=client.post(API+'/materials/upload',files={'file':(name,body)},headers=h)
    assert r.status_code==201,r.text
    return r.json()['id']


def test_document_ingestion_search_rename_isolation(client,auth_headers):
    lid=material(client,auth_headers)
    assert client.get(API+f'/lectures/{lid}/transcript',headers=auth_headers).json()['timed'] is False
    found=client.get(API+'/library/search?q=mitochondria',headers=auth_headers).json()
    assert any(x['lecture_id']==lid for x in found['items'])
    assert client.patch(API+f'/lectures/{lid}',json={'title':'Cell biology'},headers=auth_headers).status_code==200
    h=other(client)
    assert client.get(API+f'/lectures/{lid}',headers=h).status_code==404
    assert client.get(API+f'/materials/{lid}/metadata',headers=h).status_code==404
    assert client.patch(API+f'/lectures/{lid}',json={'title':'stolen'},headers=h).status_code==404
    assert client.delete(API+f'/lectures/{lid}',headers=h).status_code==404


@pytest.mark.parametrize('name,body',[('attack.exe',b'test'),('wrong.pdf',b'not pdf'),('binary.txt',b'abc\x00def'),('empty.txt',b'')])
def test_invalid_files_rejected(client,auth_headers,name,body):
    assert client.post(API+'/materials/upload',files={'file':(name,body)},headers=auth_headers).status_code==422


def test_progress_multiple_materials_persists(client,auth_headers):
    a=material(client,auth_headers);b=material(client,auth_headers)
    for lid in [a,b]:
        assert client.post(API+f'/lectures/{lid}/progress',json={'seconds':22},headers=auth_headers).status_code==200
        assert client.get(API+f'/lectures/{lid}/progress',headers=auth_headers).json()['seconds']==22


def question_bank(client,h):
    lid=material(client,h)
    with SessionLocal() as db:
        q=Quiz(lecture_id=lid,config={},mode='manual');db.add(q);db.flush()
        db.add(QuizQuestion(quiz_id=q.id,prompt='Which structure contains DNA?',options=['Nucleus','Membrane'],answer='Nucleus',explanation='Source: Cells contain a nucleus.',type='mcq',topic='Cell',difficulty='easy'))
        db.commit()
    return lid


def test_exam_authoritative_scoring_idempotency_and_privacy(client,auth_headers):
    lid=question_bank(client,auth_headers)
    r=client.post(API+'/exams',json={'lecture_ids':[lid],'count':1,'minutes':1},headers=auth_headers)
    assert r.status_code==201,r.text
    exam=r.json();eid=exam['id'];qid=str(exam['questions'][0]['id'])
    assert 'answer' not in exam['questions'][0] and exam['results']==[]
    bad=client.patch(API+f'/exams/{eid}',json={'answers':{'99999':'Nucleus'}},headers=auth_headers)
    assert bad.status_code==422
    assert client.patch(API+f'/exams/{eid}',json={'answers':{qid:'Nucleus'},'marked':[int(qid)]},headers=auth_headers).status_code==200
    assert client.get(API+f'/exams/{eid}',headers=other(client)).status_code==404
    one=client.post(API+f'/exams/{eid}/submit',json={'score':0},headers=auth_headers).json()
    two=client.post(API+f'/exams/{eid}/submit',headers=auth_headers).json()
    assert one['score']==two['score']==1
    assert one['submitted_at']==two['submitted_at']
    assert client.patch(API+f'/exams/{eid}',json={'answers':{}},headers=auth_headers).status_code==409


def test_exam_timeout_rejects_late_answers(client,auth_headers):
    lid=question_bank(client,auth_headers)
    e=client.post(API+'/exams',json={'lecture_ids':[lid],'count':1,'minutes':1},headers=auth_headers).json()
    with SessionLocal() as db:
        row=db.get(ExamSession,e['id']);row.deadline=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    late=client.patch(API+f"/exams/{e['id']}",json={'answers':{str(e['questions'][0]['id']):'Nucleus'}},headers=auth_headers)
    assert late.status_code==409
    result=client.get(API+f"/exams/{e['id']}",headers=auth_headers).json()
    assert result['submitted_at'] and result['score']==0


def test_collaboration_two_accounts_membership_and_permissions(client,auth_headers):
    h2=other(client)
    r=client.post(API+'/rooms',json={'name':'Biology circle'},headers=auth_headers).json();rid=r['id']
    assert client.get(API+f'/rooms/{rid}',headers=h2).status_code==404
    assert client.post(API+'/rooms/join',json={'code':r['invite_code']},headers=h2).status_code==200
    client.post(API+f'/rooms/{rid}/entries',json={'kind':'note','content':'Shared understanding'},headers=h2)
    entries=client.get(API+f'/rooms/{rid}',headers=auth_headers).json()['entries']
    assert entries[0]['content']=='Shared understanding'
    assert client.delete(API+f'/rooms/{rid}',headers=h2).status_code==403
    assert client.post(API+f'/rooms/{rid}/leave',headers=auth_headers).status_code==409
    assert client.post(API+f'/rooms/{rid}/leave',headers=h2).status_code==204
    assert client.get(API+f'/rooms/{rid}',headers=h2).status_code==404
    assert client.delete(API+f'/rooms/{rid}',headers=auth_headers).status_code==204


def test_memory_private_and_deletable(client,auth_headers):
    r=client.post(API+'/memory',json={'title':'Understand cells','kind':'goal','data':{}},headers=auth_headers)
    assert r.status_code==201
    mid=r.json()['id']
    assert client.delete(API+f'/memory/{mid}',headers=other(client)).status_code==404
    assert any(x['id']==mid for x in client.get(API+'/memory',headers=auth_headers).json()['records'])
    assert client.delete(API+f'/memory/{mid}',headers=auth_headers).status_code==204


def test_no_silent_ai_fallback(monkeypatch):
    from app.services.ai import AI,AIError
    from app.config import settings
    monkeypatch.setattr(settings,'allow_demo_ai',False)
    monkeypatch.setattr(settings,'gemini_api_key','')
    monkeypatch.setattr(settings,'enable_local_fallback',False)
    assert AI().mode=='unavailable'
    with pytest.raises(AIError): AI().complete_text('hello',fallback=lambda:'fabricated')
    with pytest.raises(AIError): AI().complete_json('hello',{},fallback=lambda:{'fake':True})


def test_comparison_has_source_evidence(client,auth_headers):
    a=material(client,auth_headers);b=material(client,auth_headers)
    r=client.post(API+'/materials/compare',json={'lecture_ids':[a,b]},headers=auth_headers)
    assert r.status_code==200
    assert any(x['term']=='nucleus' and len(x['evidence'])==2 for x in r.json()['common'])
    assert client.post(API+'/materials/compare',json={'lecture_ids':[a,b]},headers=other(client)).status_code==404


def test_migrations_idempotent():
    from app.migrations import migrate
    migrate();migrate()


def test_manual_notes_cards_and_logout(client,auth_headers):
    h=other(client);lid=material(client,h)
    n=client.post(API+f'/lectures/{lid}/notes/manual',json={'title':'A note','content':'My own words','timestamp':30},headers=h)
    assert n.status_code==201,n.text
    assert n.json()['content_md'].startswith('[0:30]')
    c=client.post(API+'/cards',json={'lecture_id':lid,'front':'Question','back':'Answer','topic':'My deck'},headers=h)
    assert c.status_code==201,c.text
    cid=c.json()['id']
    assert client.patch(API+f'/cards/{cid}',json={'front':'Refined question'},headers=h).status_code==200
    assert client.patch(API+f'/cards/{cid}',json={'front':'intruder'},headers=auth_headers).status_code==404
    assert client.delete(API+f'/cards/{cid}',headers=auth_headers).status_code==404
    assert client.delete(API+f'/cards/{cid}',headers=h).status_code==204
    assert client.post(API+'/auth/logout',headers=h).status_code==204
    assert client.get(API+'/auth/me',headers=h).status_code==401


def test_doubt_due_date_priority_history(client,auth_headers):
    d=client.post(API+'/doubts',json={'question':'How do cells divide?','priority':'high','due_date':'2027-01-03'},headers=auth_headers).json()
    r=client.patch(API+f"/doubts/{d['id']}",json={'status':'resolved','note':'I understand mitosis'},headers=auth_headers)
    assert r.status_code==200,r.text
    out=r.json();assert out['due_date']=='2027-01-03' and out['priority']=='high'
    assert out['history'][0]['to']=='resolved'
    r=client.patch(API+f"/doubts/{d['id']}",json={'status':'unresolved','due_date':None},headers=auth_headers).json()
    assert r['due_date'] is None and len(r['history'])==2


def test_pdf_page_metadata_and_real_extraction(client,auth_headers):
    from io import BytesIO
    from reportlab.pdfgen import canvas
    data=BytesIO();c=canvas.Canvas(data);c.drawString(40,700,'Cells contain a nucleus.');c.showPage();c.drawString(40,700,'Mitochondria produce ATP.');c.save()
    lid=material(client,auth_headers,'biology.pdf',data.getvalue())
    meta=client.get(API+f'/materials/{lid}/metadata',headers=auth_headers).json()
    assert [p['page'] for p in meta['pages']]==[1,2]
    tr=client.get(API+f'/lectures/{lid}/transcript',headers=auth_headers).json()
    assert not tr['timed'] and 'nucleus' in tr['segments'][0]['text']


def test_timezone_is_profile_driven():
    from app.routers.planner import _today
    from app.models import User
    from zoneinfo import ZoneInfo
    u=User(prefs={'timezone':'Pacific/Kiritimati'})
    assert _today(u)==datetime.now(ZoneInfo('Pacific/Kiritimati')).date()


def test_semantic_comparison_rejects_fabricated_quote(client,auth_headers,monkeypatch):
    from app.services.ai import ai
    a=material(client,auth_headers);b=material(client,auth_headers)
    monkeypatch.setattr(ai,'complete_json',lambda *args,**kwargs:({'claims':[{'relation':'common','summary':'Unsupported','sources':[{'segment_id':999999,'quote':'A fabricated passage from nowhere'}]}]},'gemini'))
    r=client.post(API+'/materials/compare/ai',json={'lecture_ids':[a,b]},headers=auth_headers)
    assert r.status_code==503 and 'unverifiable' in r.json()['detail']


def test_legacy_watch_migration_preserves_data(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,text
    from app.database import Base
    from app import migrations
    legacy=create_engine(f"sqlite:///{tmp_path}/legacy.db")
    Base.metadata.create_all(legacy)
    with legacy.begin() as c:
        c.execute(text('DROP TABLE watch_progress'))
        c.execute(text('CREATE TABLE watch_progress (id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,lecture_id INTEGER NOT NULL,seconds FLOAT NOT NULL,updated_at DATETIME NOT NULL)'))
        c.execute(text('CREATE UNIQUE INDEX ix_watch_progress_user_id ON watch_progress(user_id)'))
        c.execute(text('CREATE UNIQUE INDEX ix_watch_progress_lecture_id ON watch_progress(lecture_id)'))
        c.execute(text("INSERT INTO watch_progress VALUES(7,1,2,95,'2026-11-15 00:00:00')"))
    monkeypatch.setattr(migrations,'engine',legacy)
    migrations.migrate();migrations.migrate()
    with legacy.connect() as c:
        row=c.execute(text('SELECT id,seconds,resume_seconds FROM watch_progress')).first()
        assert tuple(row)==(7,95,95)
        assert c.execute(text('SELECT count(*) FROM schema_versions')).scalar()==5
    legacy.dispose()


def test_highlight_persistence_and_cross_user_source_validation(client,auth_headers):
    lid=material(client,auth_headers)
    r=client.post(API+'/memory',json={'kind':'highlight','title':'A source highlight','data':{'lecture_id':lid,'content':'Cells contain a nucleus.'}},headers=auth_headers)
    assert r.status_code==201
    r=client.post(API+'/memory',json={'kind':'highlight','title':'Bad source access','data':{'lecture_id':lid,'content':'Copied'}},headers=other(client))
    assert r.status_code==404


def test_planner_skip_move_capacity_and_recalculate(client,auth_headers):
    from app.routers.planner import _today
    lid=material(client,auth_headers)
    future=(_today()+timedelta(days=12)).isoformat()
    plan=client.post(API+'/planner/plans',json={'title':'Cell revision','exam_date':future,'daily_minutes':45,'lecture_ids':[lid]},headers=auth_headers).json()
    tid=plan['tasks'][0]['id']
    assert client.patch(API+f'/planner/tasks/{tid}',json={'status':'skipped'},headers=auth_headers).status_code==422
    assert client.patch(API+f'/planner/tasks/{tid}',json={'status':'skipped','reason':'Already studied this source'},headers=auth_headers).json()['status']=='skipped'
    moved=(_today()+timedelta(days=2)).isoformat()
    t2=plan['tasks'][1]['id']
    assert client.patch(API+f'/planner/tasks/{t2}',json={'day':moved},headers=auth_headers).json()['day']==moved
    r=client.post(API+f"/planner/plans/{plan['id']}/recalculate",json={'daily_minutes':60},headers=auth_headers)
    assert r.status_code==200 and r.json()['daily_minutes']==60


def test_room_edit_policy_and_invite_rotation(client,auth_headers):
    h2=other(client)
    room=client.post(API+'/rooms',json={'name':'Two students'},headers=auth_headers).json();rid=room['id']
    assert client.post(API+'/rooms/join',json={'code':room['invite_code']},headers=h2).status_code==200
    r=client.post(API+f'/rooms/{rid}/entries',json={'content':'Owner note'},headers=auth_headers).json()
    eid=r['entries'][0]['id']
    assert client.patch(API+f'/rooms/{rid}/entries/{eid}',json={'content':'Hijack'},headers=h2).status_code==403
    assert client.post(API+f'/rooms/{rid}/rotate-invite',headers=h2).status_code==403
    updated=client.post(API+f'/rooms/{rid}/rotate-invite',headers=auth_headers).json()
    assert updated['invite_code']!=room['invite_code']
    assert client.post(API+'/rooms/join',json={'code':room['invite_code']},headers=other(client)).status_code==404
    assert client.delete(API+f'/rooms/{rid}/members/'+str(client.get(API+'/auth/me',headers=h2).json()['id']),headers=auth_headers).status_code==204
    assert client.get(API+f'/rooms/{rid}',headers=h2).status_code==404


def test_profile_invalid_timezone_and_availability(client,auth_headers):
    assert client.patch(API+'/auth/profile',json={'prefs':{'timezone':'Invalid/Timezone'}},headers=auth_headers).status_code==422
    assert client.patch(API+'/auth/profile',json={'prefs':{'daily_minutes':-1}},headers=auth_headers).status_code==422
