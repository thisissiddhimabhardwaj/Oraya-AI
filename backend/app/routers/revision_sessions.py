"""Resumable, server-authoritative recall sessions over the real SM-2 card queue."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import Flashcard,ReviewLog,RevisionSession,RevisionResponse,User,StudyPlan
from ..services.srs import next_schedule,maturity,RELEARN_MINUTES
from ..config import settings
router=APIRouter(prefix='/revision',tags=['revision sessions'])
def aware(t):return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
def now():return datetime.now(timezone.utc)
def owned(db,u,sid):
    s=db.get(RevisionSession,sid)
    if not s or s.user_id!=u.id:raise HTTPException(404,'Revision session not found')
    return s

def session_out(db,s):
    while s.cursor<len(s.card_ids):
        candidate=db.get(Flashcard,s.card_ids[s.cursor])
        if candidate and candidate.user_id==s.user_id:break
        s.cursor+=1
    if s.cursor>=len(s.card_ids):s.status='completed'
    db.commit()
    card=db.get(Flashcard,s.card_ids[s.cursor]) if s.status=='active' else None
    responses=db.scalars(select(RevisionResponse).where(RevisionResponse.session_id==s.id).order_by(RevisionResponse.id)).all()
    current=None
    if card:
        saved=s.answers.get(str(card.id))
        current={'id':card.id,'lecture_id':card.lecture_id,'topic':card.topic,'front':card.front,'reps':card.reps,'due_at':aware(card.due_at).isoformat(),'answer':saved,'back':card.back if saved is not None else None}
    return {'id':s.id,'status':s.status,'cursor':s.cursor,'total':len(s.card_ids),'current':current,'responses':[{'card_id':r.card_id,'answer':r.answer,'quality':r.quality,'next_due':aware(r.next_due).isoformat(),'created_at':aware(r.created_at).isoformat()} for r in responses]}

@router.get('/overview')
def overview(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    zone=ZoneInfo((user.prefs or {}).get('timezone',settings.study_timezone));today=now().astimezone(zone).date()
    cards=db.scalars(select(Flashcard).where(Flashcard.user_id==user.id)).all()
    logs=db.scalars(select(ReviewLog).where(ReviewLog.user_id==user.id).order_by(ReviewLog.id.desc())).all()
    latest={}
    for l in logs:latest.setdefault(l.flashcard_id,l)
    exam=(user.prefs or {}).get('exam_date')
    plans=db.scalars(select(StudyPlan).where(StudyPlan.user_id==user.id)).all()
    def exam_boost(c):
        dates=[p.exam_date for p in plans if c.lecture_id in p.lecture_ids and p.exam_date>=today.isoformat()]
        if exam and exam>=today.isoformat():dates.append(exam)
        if not dates:return 0
        remaining=(datetime.fromisoformat(min(dates)).date()-today).days
        return max(0,14-remaining)/3
    def priority(c):
        overdue=max(0,(now()-aware(c.due_at)).total_seconds()/86400)
        lapse=1 if c.id in latest and latest[c.id].quality<2 else 0
        return overdue*2+lapse*4+max(0,2.5-c.ease)*2+exam_boost(c)
    def card(c):return {'id':c.id,'lecture_id':c.lecture_id,'topic':c.topic,'front':c.front,'due_at':aware(c.due_at).isoformat(),'reviews':sum(l.flashcard_id==c.id for l in logs),'ease':c.ease,'stage':maturity(c.reps,c.interval_days),'last_reviewed':aware(latest[c.id].created_at).isoformat() if c.id in latest else None}
    due=sorted((c for c in cards if aware(c.due_at)<=now()),key=priority,reverse=True)
    upcoming=sorted((c for c in cards if aware(c.due_at)>now()),key=lambda c:aware(c.due_at))
    calendar={}
    for c in cards:
        day=aware(c.due_at).astimezone(zone).date().isoformat();calendar[day]=calendar.get(day,0)+1
    return {'due':[card(c) for c in due],'overdue':sum(aware(c.due_at).astimezone(zone).date()<today for c in due),'upcoming':[card(c) for c in upcoming],'weak':[card(c) for c in cards if c.id in latest and latest[c.id].quality<2],'mastered':[card(c) for c in cards if maturity(c.reps,c.interval_days)=='mature'],'calendar':[{'date':d,'cards':n} for d,n in sorted(calendar.items())],'history':[{'id':l.id,'card_id':l.flashcard_id,'quality':l.quality,'next_interval':l.interval_after,'created_at':aware(l.created_at).isoformat()} for l in logs[:100]],'total':len(cards),'method':'SM-2. Queue priority combines overdue days, last recall quality and ease; exam proximity boosts material linked to an upcoming plan. Recall ratings are self-assessments, not objective quiz scores.'}

@router.get('/sessions/active')
def active(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    s=db.scalar(select(RevisionSession).where(RevisionSession.user_id==user.id,RevisionSession.status=='active').order_by(RevisionSession.id.desc()))
    return session_out(db,s) if s else None

class StartIn(BaseModel):limit:int=Field(default=20,ge=1,le=100)
@router.post('/sessions',status_code=201)
def start(p:StartIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    s=db.scalar(select(RevisionSession).where(RevisionSession.user_id==user.id,RevisionSession.status=='active').order_by(RevisionSession.id.desc()))
    if s:return session_out(db,s)
    ids=[c['id'] for c in overview(user,db)['due'][:p.limit]]
    if not ids:raise HTTPException(409,'No concepts are due. Create cards from a lecture or return on the next scheduled date.')
    from sqlalchemy.exc import IntegrityError
    s=RevisionSession(user_id=user.id,card_ids=ids);db.add(s)
    try:db.commit()
    except IntegrityError:
        db.rollback();s=db.scalar(select(RevisionSession).where(RevisionSession.user_id==user.id,RevisionSession.status=='active'))
        if not s:raise HTTPException(409,'Could not start a session; retry')
    return session_out(db,s)

@router.get('/sessions/{sid}')
def get_session(sid:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):return session_out(db,owned(db,user,sid))
class RecallIn(BaseModel):
    card_id:int
    answer:str=Field(min_length=1,max_length=4000)
@router.post('/sessions/{sid}/reveal')
def reveal(sid:int,p:RecallIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    s=owned(db,user,sid)
    if s.status!='active' or s.cursor>=len(s.card_ids) or s.card_ids[s.cursor]!=p.card_id:raise HTTPException(409,'This is not the current revision card')
    if str(p.card_id) not in s.answers:s.answers={**s.answers,str(p.card_id):p.answer};db.commit()
    return session_out(db,s)
class RateIn(BaseModel):
    card_id:int
    quality:int=Field(ge=0,le=3)
@router.post('/sessions/{sid}/rate')
def rate(sid:int,p:RateIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    s=owned(db,user,sid)
    existing=db.scalar(select(RevisionResponse).where(RevisionResponse.session_id==sid,RevisionResponse.card_id==p.card_id))
    if existing:return session_out(db,s)
    if s.status!='active' or s.cursor>=len(s.card_ids) or s.card_ids[s.cursor]!=p.card_id or str(p.card_id) not in s.answers:raise HTTPException(409,'Answer and reveal the current card before rating recall')
    c=db.get(Flashcard,p.card_id)
    if not c or c.user_id!=user.id:raise HTTPException(404,'Card no longer available')
    cursor=s.cursor
    claimed=db.execute(update(RevisionSession).where(RevisionSession.id==sid,RevisionSession.cursor==cursor).values(cursor=cursor+1).execution_options(synchronize_session=False))
    if not claimed.rowcount:db.rollback();raise HTTPException(409,'Session changed; reload to continue')
    before=c.interval_days;sch=next_schedule(c.reps,c.ease,c.interval_days,p.quality)
    c.reps,c.ease,c.interval_days=sch.reps,sch.ease,sch.interval_days;c.due_at=now()+(timedelta(minutes=RELEARN_MINUTES) if sch.lapsed else timedelta(days=sch.interval_days))
    db.add(ReviewLog(user_id=user.id,flashcard_id=c.id,quality=p.quality,interval_before=before,interval_after=sch.interval_days,ease_after=sch.ease))
    db.add(RevisionResponse(user_id=user.id,session_id=sid,card_id=c.id,answer=s.answers[str(c.id)],quality=p.quality,next_due=c.due_at));db.commit();db.refresh(s);return session_out(db,s)
