"""AI Study Planner — a deterministic, explainable scheduler driven by the student's real data.

Inputs: chosen lectures, exam date, daily minutes, topic mastery, due flashcards.
No LLM is used to place tasks: the schedule must be reproducible and auditable. Each lecture gets a
'watch' task followed by spaced 'revise' tasks (+1, +3, +7 days); weak topics get extra practice;
missed tasks are rescheduled into the earliest day with spare capacity before the exam.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from zoneinfo import ZoneInfo
from ..database import get_db
from ..deps import get_current_user
from ..models import Lecture, StudyPlan, StudyTask, Topic, TopicMastery, User

router = APIRouter(prefix="/planner", tags=["planner"])
REVISION_OFFSETS = (1, 3, 7)
WEAK_BELOW = 0.6


class PlanIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    exam_date: date
    daily_minutes: int = Field(default=60, ge=15, le=480)
    lecture_ids: list[int] = Field(min_length=1)


class TaskPatch(BaseModel):
    status: str | None = Field(default=None,pattern="^(pending|done|skipped)$")
    day: date | None = None
    reason: str = Field(default="",max_length=500)


def _today(user: User | None = None) -> date:
    zone=(user.prefs or {}).get("timezone",settings.study_timezone) if user else settings.study_timezone
    try: return datetime.now(ZoneInfo(zone)).date()
    except (KeyError,ValueError,TypeError): return datetime.now(ZoneInfo(settings.study_timezone)).date()


def _load(db: Session, user: User, plan_id: int) -> StudyPlan:
    p = db.get(StudyPlan, plan_id)
    if p is None or p.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    return p


def _task_out(t: StudyTask, user: User | None = None) -> dict:
    return {"id": t.id, "day": t.day, "kind": t.kind, "title": t.title, "lecture_id": t.lecture_id,
            "topic": t.topic, "minutes": t.minutes, "status": t.status, "rescheduled": bool(t.rescheduled), "reason":t.reason,
            "overdue": t.status == "pending" and t.day < _today(user).isoformat()}


def _plan_out(p: StudyPlan, user: User | None = None) -> dict:
    tasks = sorted(p.tasks, key=lambda t: (t.day, t.id))
    done = sum(1 for t in tasks if t.status == "done")
    return {"id": p.id, "title": p.title, "exam_date": p.exam_date, "daily_minutes": p.daily_minutes,
            "lecture_ids": p.lecture_ids, "tasks": [_task_out(t,user) for t in tasks],
            "progress": {"done": done, "total": len(tasks), "overdue": sum(1 for t in tasks if t.status == "pending" and t.day < _today(user).isoformat())}}


def _place(load: dict[str, int], start: date, last: date, minutes: int, cap: int) -> date:
    """Earliest day in [start,last] with room; if the window is full, the least-loaded day."""
    start = min(start, last)
    d = start
    while d <= last:
        if load.get(d.isoformat(), 0) + minutes <= cap:
            return d
        d += timedelta(days=1)
    raise HTTPException(409,"Not enough available time before this exam. Increase daily minutes, choose fewer materials, or move the exam date.")


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    today = _today(user)
    if payload.exam_date <= today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The exam date must be in the future")
    lectures = db.scalars(select(Lecture).where(Lecture.user_id == user.id, Lecture.id.in_(payload.lecture_ids))).all()
    if len(lectures) != len(set(payload.lecture_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more lectures were not found")

    plan = StudyPlan(user_id=user.id, title=payload.title, exam_date=payload.exam_date.isoformat(),
                     daily_minutes=payload.daily_minutes, lecture_ids=[l.id for l in lectures])
    db.add(plan)
    db.flush()
    last = payload.exam_date - timedelta(days=1)
    load: dict[str, int] = {}
    tasks: list[StudyTask] = []

    def add(day: date, kind: str, title: str, lec: Lecture, minutes: int, topic: str = "") -> None:
        load[day.isoformat()] = load.get(day.isoformat(), 0) + minutes
        tasks.append(StudyTask(plan_id=plan.id, user_id=user.id, day=day.isoformat(), kind=kind, title=title,
                               lecture_id=lec.id, topic=topic, minutes=minutes))

    for lec in sorted(lectures, key=lambda l: l.id):
        watch = max(10, min(payload.daily_minutes, round((lec.duration or 1200) / 60)))
        d0 = _place(load, today, last, watch, payload.daily_minutes)
        add(d0, "watch", f"Watch: {lec.title}", lec, watch)
        for off in REVISION_OFFSETS:
            d = d0 + timedelta(days=off)
            if d <= last:
                add(_place(load, d, last, 15, payload.daily_minutes), "revise", f"Revise flashcards & notes: {lec.title}", lec, 15)
        weak = db.scalars(select(Topic).join(TopicMastery, TopicMastery.topic_id == Topic.id)
                          .where(Topic.lecture_id == lec.id, TopicMastery.user_id == user.id,
                                 TopicMastery.score < WEAK_BELOW)).all()
        for t in weak[:3]:
            add(_place(load, d0 + timedelta(days=2), last, 20, payload.daily_minutes), "practice",
                f"Practise weak topic: {t.name}", lec, 20, t.name)
    db.add_all(tasks)
    db.commit()
    db.refresh(plan)
    return _plan_out(plan,user)


@router.get("/plans")
def list_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    plans = db.scalars(select(StudyPlan).where(StudyPlan.user_id == user.id).order_by(StudyPlan.id.desc())).all()
    return {"items": [_plan_out(p,user) for p in plans]}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return _plan_out(_load(db, user, plan_id),user)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_load(db, user, plan_id))
    db.commit()


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, payload: TaskPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    t = db.get(StudyTask, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    plan=_load(db,user,t.plan_id)
    if payload.day:
        if payload.day < _today(user) or payload.day >= date.fromisoformat(plan.exam_date):
            raise HTTPException(422,"Choose a date from today until the day before the exam")
        used=sum(x.minutes for x in plan.tasks if x.id!=t.id and x.day==payload.day.isoformat() and x.status in ('pending','done'))
        if used+t.minutes>plan.daily_minutes:raise HTTPException(409,'This day exceeds your available study time. Rebalance the plan or choose another date.')
        t.day=payload.day.isoformat();t.rescheduled+=1
    if payload.status=="skipped" and not payload.reason.strip():raise HTTPException(422,"A skipped task needs a reason")
    if payload.status:t.status=payload.status
    t.reason=payload.reason
    db.commit()
    return _task_out(t,user)


@router.post("/plans/{plan_id}/reschedule")
def reschedule(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Move every unfinished task from a past day into the earliest day with spare capacity before the exam."""
    plan = _load(db, user, plan_id)
    today, last = _today(user), date.fromisoformat(plan.exam_date) - timedelta(days=1)
    if last < today:
        raise HTTPException(status.HTTP_409_CONFLICT, "The exam date has passed")
    overdue = [t for t in plan.tasks if t.status == "pending" and t.day < today.isoformat()]
    load: dict[str, int] = {}
    for t in plan.tasks:
        if t.status != "done" and t not in overdue:
            load[t.day] = load.get(t.day, 0) + t.minutes
    moved = 0
    for t in sorted(overdue, key=lambda x: x.day):
        t.day = _place(load, today, last, t.minutes, plan.daily_minutes).isoformat()
        load[t.day] = load.get(t.day, 0) + t.minutes
        t.rescheduled += 1
        moved += 1
    db.commit()
    return {**_plan_out(plan,user), "moved": moved}


class RecalculateIn(BaseModel):
    daily_minutes:int=Field(ge=15,le=480)
    exam_date:date|None=None


@router.post('/plans/{plan_id}/recalculate')
def recalculate(plan_id:int,p:RecalculateIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    plan=_load(db,user,plan_id)
    today=_today(user);last=(p.exam_date or date.fromisoformat(plan.exam_date))-timedelta(days=1)
    if last<today:raise HTTPException(422,'Exam must be in the future')
    load={}
    for t in plan.tasks:
        if t.status=='done':load[t.day]=load.get(t.day,0)+t.minutes
    for t in sorted((x for x in plan.tasks if x.status=='pending'),key=lambda x:(x.day,x.id)):
        t.day=_place(load,today,last,t.minutes,p.daily_minutes).isoformat()
        load[t.day]=load.get(t.day,0)+t.minutes;t.rescheduled+=1
    plan.daily_minutes=p.daily_minutes
    if p.exam_date:plan.exam_date=p.exam_date.isoformat()
    db.commit();return _plan_out(plan,user)
