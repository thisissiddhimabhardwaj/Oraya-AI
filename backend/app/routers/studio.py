"""Persistent assessment, collaboration and inspectable learning memory.
All records are authenticated and scoped by ownership or explicit room membership.
"""
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import (User, Lecture, Quiz, QuizQuestion, ExamSession, StudyRoom, RoomMember,
                      RoomEntry, LearningRecord, QuizAttempt, ReviewLog, WatchProgress, TopicMastery, Topic)
from ..services.lecture_service import get_owned_lecture
from .quiz import _norm

router = APIRouter(tags=['studio'])


def now():
    return datetime.now(timezone.utc)


def aware(d):
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


class ExamIn(BaseModel):
    title: str = Field(default='Practice exam', min_length=1, max_length=160)
    lecture_ids: list[int] = Field(min_length=1, max_length=30)
    count: int = Field(default=10, ge=1, le=50)
    minutes: int = Field(default=20, ge=1, le=180)
    difficulty: Literal['all','easy','medium','hard'] = 'all'
    topics: list[str] = Field(default_factory=list, max_length=30)


class AnswersIn(BaseModel):
    answers: dict[str,str] = Field(default_factory=dict, max_length=50)
    marked: list[int] = Field(default_factory=list, max_length=50)


def owned_exam(db, user, eid):
    e = db.get(ExamSession, eid)
    if not e or e.user_id != user.id:
        raise HTTPException(404, 'Exam not found')
    return e


def finish(db, e):
    if e.submitted_at:
        return
    results = []
    for qid in e.question_ids:
        q = db.get(QuizQuestion, qid)
        if not q:
            raise HTTPException(409, 'The source quiz was removed. This exam cannot be scored.')
        answer = e.answers.get(str(q.id), '')
        # Exams use MCQ only; the server alone holds and compares correct answers.
        results.append({'question_id': q.id, 'prompt': q.prompt, 'answer': answer,
                        'correct': _norm(answer) == _norm(q.answer), 'correct_answer': q.answer,
                        'explanation': q.explanation, 'topic': q.topic})
    score = sum(r['correct'] for r in results) / max(1,len(results))
    # Atomic claim makes concurrent submissions idempotent.
    claimed = db.execute(update(ExamSession).where(ExamSession.id == e.id, ExamSession.submitted_at.is_(None))
                         .values(submitted_at=now(), score=score, results=results).execution_options(synchronize_session=False))
    db.commit()
    db.refresh(e)


def exam_out(db, e):
    if not e.submitted_at and now() >= aware(e.deadline):
        finish(db, e)
    questions=[]
    for qid in e.question_ids:
        q=db.get(QuizQuestion,qid)
        if q:
            questions.append({'id':q.id,'prompt':q.prompt,'options':q.options,'topic':q.topic,'difficulty':q.difficulty})
    return {'id':e.id,'title':e.title,'questions':questions,'answers':e.answers,'marked':e.marked,
            'deadline':aware(e.deadline).isoformat(),'server_now':now().isoformat(),
            'submitted_at':e.submitted_at,'score':e.score,'results':e.results if e.submitted_at else []}


@router.post('/exams', status_code=201)
def start_exam(p:ExamIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    for lid in p.lecture_ids:
        get_owned_lecture(db,user,lid)
    stmt=select(QuizQuestion).join(Quiz).where(Quiz.lecture_id.in_(p.lecture_ids),QuizQuestion.type=='mcq')
    if p.difficulty!='all': stmt=stmt.where(QuizQuestion.difficulty==p.difficulty)
    if p.topics: stmt=stmt.where(QuizQuestion.topic.in_(p.topics))
    qs=db.scalars(stmt.order_by(QuizQuestion.id.desc())).all()
    # No silently fabricated questions when an AI provider is unavailable.
    qs=list({q.prompt:q for q in qs}.values())[:p.count]
    if len(qs)<p.count:
        raise HTTPException(409,f'Only {len(qs)} matching multiple-choice questions are saved. Generate a quiz in the lecture workspace or reduce the count.')
    e=ExamSession(user_id=user.id,title=p.title,question_ids=[q.id for q in qs],deadline=now()+timedelta(minutes=p.minutes))
    db.add(e);db.commit();return exam_out(db,e)


@router.get('/exams')
def exams(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return {'items':[exam_out(db,e) for e in db.scalars(select(ExamSession).where(ExamSession.user_id==user.id).order_by(ExamSession.id.desc())).all()]}


@router.get('/exams/{eid}')
def get_exam(eid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return exam_out(db,owned_exam(db,user,eid))


@router.patch('/exams/{eid}')
def save_exam(eid:int,p:AnswersIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    e=owned_exam(db,user,eid)
    if e.submitted_at or now()>=aware(e.deadline):
        finish(db,e);raise HTTPException(409,'Exam is already submitted or its time has expired')
    valid={str(i) for i in e.question_ids}
    if set(p.answers)-valid or set(p.marked)-set(e.question_ids): raise HTTPException(422,'Unknown question')
    for key,value in p.answers.items():
        q=db.get(QuizQuestion,int(key))
        if value and value not in (q.options or []): raise HTTPException(422,'Answer must be one of the provided options')
    # Conditional update prevents a late save overwriting a concurrently submitted exam.
    changed=db.execute(update(ExamSession).where(ExamSession.id==e.id,ExamSession.submitted_at.is_(None),ExamSession.deadline>now())
                       .values(answers=p.answers,marked=p.marked).execution_options(synchronize_session=False))
    db.commit();db.refresh(e)
    if not changed.rowcount: raise HTTPException(409,'Exam closed while saving')
    return exam_out(db,e)


@router.post('/exams/{eid}/submit')
def submit_exam(eid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    e=owned_exam(db,user,eid);finish(db,e);return exam_out(db,e)


class RoomIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)


class JoinIn(BaseModel):
    code:str=Field(min_length=12,max_length=64)


class EntryIn(BaseModel):
    kind:Literal['note','goal','quiz']='note'
    content:str=Field(min_length=1,max_length=10000)


class EntryPatch(BaseModel):
    content:str|None=Field(default=None,min_length=1,max_length=10000)
    completed:bool|None=None


def room_access(db,user,rid):
    r=db.get(StudyRoom,rid)
    member=db.scalar(select(RoomMember).where(RoomMember.room_id==rid,RoomMember.user_id==user.id))
    if not r or not member: raise HTTPException(404,'Room not found')
    return r


def room_out(db,r,user,detail=False):
    members=db.scalars(select(RoomMember).where(RoomMember.room_id==r.id)).all()
    out={'id':r.id,'name':r.name,'owner_id':r.owner_id,'is_owner':r.owner_id==user.id,
         'invite_code':r.invite_code,'member_count':len(members)}
    if detail:
        rows=db.scalars(select(RoomEntry).where(RoomEntry.room_id==r.id).order_by(RoomEntry.id)).all()
        out['entries']=[{'id':e.id,'user_id':e.user_id,'author':db.get(User,e.user_id).name,'kind':e.kind,
                          'content':e.content,'completed':bool(e.completed),'created_at':aware(e.created_at).isoformat()} for e in rows]
    return out


@router.post('/rooms',status_code=201)
def create_room(p:RoomIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=StudyRoom(name=p.name,owner_id=user.id,invite_code=token_urlsafe(24));db.add(r);db.flush()
    db.add(RoomMember(room_id=r.id,user_id=user.id));db.commit();return room_out(db,r,user,True)


@router.post('/rooms/join')
def join_room(p:JoinIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=db.scalar(select(StudyRoom).where(StudyRoom.invite_code==p.code))
    if not r: raise HTTPException(404,'Invalid invite code')
    if not db.scalar(select(RoomMember).where(RoomMember.room_id==r.id,RoomMember.user_id==user.id)):
        db.add(RoomMember(room_id=r.id,user_id=user.id));db.commit()
    return room_out(db,r,user,True)


@router.get('/rooms')
def list_rooms(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rs=db.scalars(select(StudyRoom).join(RoomMember,RoomMember.room_id==StudyRoom.id).where(RoomMember.user_id==user.id)).all()
    return {'items':[room_out(db,r,user) for r in rs]}


@router.get('/rooms/{rid}')
def get_room(rid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return room_out(db,room_access(db,user,rid),user,True)


@router.post('/rooms/{rid}/entries',status_code=201)
def add_entry(rid:int,p:EntryIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    room_access(db,user,rid)
    if p.kind=='quiz':
        # Shared quiz is a source-backed snapshot. Correct answers remain private until
        # members explicitly reveal them in the room; no access to the owner's library.
        try: qid=int(p.content)
        except ValueError: raise HTTPException(422,'Choose a saved quiz ID')
        q=db.get(Quiz,qid)
        if not q: raise HTTPException(404,'Quiz not found')
        get_owned_lecture(db,user,q.lecture_id)
        import json
        content=json.dumps({'title':db.get(Lecture,q.lecture_id).title,'questions':[{'prompt':x.prompt,'options':x.options,'answer':x.answer,'explanation':x.explanation} for x in q.questions]})
    else: content=p.content
    db.add(RoomEntry(room_id=rid,user_id=user.id,kind=p.kind,content=content));db.commit()
    return room_out(db,room_access(db,user,rid),user,True)


@router.patch('/rooms/{rid}/entries/{eid}')
def edit_entry(rid:int,eid:int,p:EntryPatch,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=room_access(db,user,rid);e=db.get(RoomEntry,eid)
    if not e or e.room_id!=rid: raise HTTPException(404,'Entry not found')
    if e.user_id!=user.id and r.owner_id!=user.id: raise HTTPException(403,'Only the author or room owner may edit this entry')
    if p.content is not None:
        if e.kind=='quiz': raise HTTPException(422,'Shared quiz snapshots cannot be edited')
        e.content=p.content
    if p.completed is not None: e.completed=int(p.completed)
    db.commit();return room_out(db,r,user,True)


@router.post('/rooms/{rid}/leave',status_code=204)
def leave_room(rid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=room_access(db,user,rid)
    if r.owner_id==user.id: raise HTTPException(409,'The owner must delete the room instead of leaving')
    db.execute(delete(RoomMember).where(RoomMember.room_id==rid,RoomMember.user_id==user.id));db.commit()


@router.delete('/rooms/{rid}',status_code=204)
def delete_room(rid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=room_access(db,user,rid)
    if r.owner_id!=user.id: raise HTTPException(403,'Only the owner may delete this room')
    db.delete(r);db.commit()


class MemoryIn(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    kind:Literal['goal','explanation','correction','library_chat','doubt_metadata','highlight']='goal'
    data:dict=Field(default_factory=dict)


@router.get('/memory')
def memory(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    records=db.scalars(select(LearningRecord).where(LearningRecord.user_id==user.id).order_by(LearningRecord.id.desc())).all()
    attempts=db.scalars(select(QuizAttempt).where(QuizAttempt.user_id==user.id)).all()
    reviews=db.scalars(select(ReviewLog).where(ReviewLog.user_id==user.id)).all()
    topics=db.execute(select(TopicMastery.id,Topic.name,TopicMastery.score).join(TopicMastery).where(TopicMastery.user_id==user.id)).all()
    return {'preferences':user.prefs,'subjects':user.subjects,
            'records':[{'id':r.id,'title':r.title,'kind':r.kind,'data':r.data,'created_at':aware(r.created_at).isoformat()} for r in records],
            'evidence':{'quiz_attempts':len(attempts),'reviews':len(reviews),'topics':[{'id':tid,'topic':t,'mastery':s} for tid,t,s in topics], 'quiz_history':[{'id':a.id,'quiz_id':a.quiz_id,'score':a.score,'results':a.results,'created_at':aware(a.created_at).isoformat()} for a in attempts[-50:]], 'review_history':[{'id':r.id,'flashcard_id':r.flashcard_id,'quality':r.quality,'next_interval_days':r.interval_after,'created_at':aware(r.created_at).isoformat()} for r in reviews[-100:]]},
            'method':'Topic mastery uses quiz correctness: initial score, then 60% previous / 40% latest attempt. No sensitive traits are inferred.'}


@router.post('/memory',status_code=201)
def save_memory(p:MemoryIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    import json
    if len(json.dumps(p.data))>100000: raise HTTPException(413,'Record is too large')
    if p.data.get('lecture_id') is not None:
        if not isinstance(p.data['lecture_id'],int) or p.data['lecture_id']<1:raise HTTPException(422,'Material ID must be a positive integer')
        get_owned_lecture(db,user,p.data['lecture_id'])
    r=LearningRecord(user_id=user.id,**p.model_dump());db.add(r);db.commit();return {'id':r.id}


@router.delete('/memory/{mid}',status_code=204)
def delete_memory(mid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=db.get(LearningRecord,mid)
    if not r or r.user_id!=user.id: raise HTTPException(404,'Record not found')
    db.delete(r);db.commit()


@router.delete('/memory',status_code=204)
def clear_memory(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    # Explicitly scoped memory reset: source materials and room contributions are retained.
    for model in [LearningRecord,TopicMastery,ReviewLog,QuizAttempt,WatchProgress,ExamSession]:
        db.execute(delete(model).where(model.user_id==user.id))
    user.prefs={};db.commit()


class CardIn(BaseModel):
    lecture_id:int
    front:str=Field(min_length=1,max_length=2000)
    back:str=Field(min_length=1,max_length=6000)
    topic:str=Field(default="My deck",max_length=120)


class CardPatch(BaseModel):
    front:str|None=Field(default=None,min_length=1,max_length=2000)
    back:str|None=Field(default=None,min_length=1,max_length=6000)
    topic:str|None=Field(default=None,max_length=120)


@router.post('/cards',status_code=201)
def create_card(p:CardIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from ..models import Flashcard
    from ..schemas import FlashcardOut
    get_owned_lecture(db,user,p.lecture_id)
    c=Flashcard(user_id=user.id,**p.model_dump());db.add(c);db.commit()
    return FlashcardOut.model_validate(c)


@router.patch('/cards/{cid}')
def edit_card(cid:int,p:CardPatch,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from ..models import Flashcard
    from ..schemas import FlashcardOut
    c=db.get(Flashcard,cid)
    if not c or c.user_id!=user.id: raise HTTPException(404,'Card not found')
    for k,v in p.model_dump(exclude_unset=True,exclude_none=True).items():setattr(c,k,v)
    db.commit();return FlashcardOut.model_validate(c)


@router.delete('/cards/{cid}',status_code=204)
def remove_card(cid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from ..models import Flashcard
    c=db.get(Flashcard,cid)
    if not c or c.user_id!=user.id:raise HTTPException(404,'Card not found')
    db.delete(c);db.commit()


class ManualNoteIn(BaseModel):
    title:str=Field(min_length=1,max_length=512)
    content:str=Field(min_length=1,max_length=20000)
    timestamp:float|None=Field(default=None,ge=0,le=86400)


@router.post('/lectures/{lid}/notes/manual',status_code=201)
def manual_note(lid:int,p:ManualNoteIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from ..models import Note
    from ..schemas import NoteOut
    get_owned_lecture(db,user,lid)
    content=(f"[{int(p.timestamp)//60}:{int(p.timestamp)%60:02d}] " if p.timestamp is not None else "")+p.content
    n=Note(lecture_id=lid,title=p.title,content_md=content,kind='manual',mode='manual');db.add(n);db.commit()
    return NoteOut.model_validate(n)


@router.post('/rooms/{rid}/rotate-invite')
def rotate_invite(rid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=room_access(db,user,rid)
    if r.owner_id!=user.id:raise HTTPException(403,'Only the room owner can rotate invitations')
    r.invite_code=token_urlsafe(24);db.commit();return room_out(db,r,user,True)


@router.get('/rooms/{rid}/members')
def room_members(rid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=room_access(db,user,rid)
    rows=db.scalars(select(RoomMember).where(RoomMember.room_id==rid)).all()
    return {'items':[{'user_id':m.user_id,'name':db.get(User,m.user_id).name,'is_owner':m.user_id==r.owner_id} for m in rows]}


@router.delete('/rooms/{rid}/members/{uid}',status_code=204)
def remove_member(rid:int,uid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    r=room_access(db,user,rid)
    if r.owner_id!=user.id:raise HTTPException(403,'Only the room owner can remove members')
    if uid==r.owner_id:raise HTTPException(409,'The owner cannot be removed')
    db.execute(delete(RoomMember).where(RoomMember.room_id==rid,RoomMember.user_id==uid));db.commit()


@router.delete('/memory/evidence/{kind}/{eid}',status_code=204)
def delete_evidence(kind:str,eid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    model={'quiz':QuizAttempt,'review':ReviewLog,'mastery':TopicMastery}.get(kind)
    if model is None:raise HTTPException(422,'Unknown evidence type')
    row=db.get(model,eid)
    if not row or row.user_id!=user.id:raise HTTPException(404,'Evidence not found')
    db.delete(row);db.commit()
