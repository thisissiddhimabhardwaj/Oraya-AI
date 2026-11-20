"""Doubt Tracker — save a question (optionally pinned to a lecture timestamp), track it, turn it into a card."""
from __future__ import annotations

from datetime import date,datetime,timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Doubt, Flashcard, Lecture, User
from ..schemas import FlashcardOut
from ..services.lecture_service import get_owned_lecture

router = APIRouter(prefix="/doubts", tags=["doubts"])
DoubtStatus = Literal["unresolved", "in_progress", "resolved"]


class DoubtIn(BaseModel):
    due_date: date | None = None
    priority: Literal["low","normal","high"] = "normal"
    question: str = Field(min_length=3, max_length=2000)
    lecture_id: int | None = None
    timestamp: float | None = Field(default=None, ge=0)
    subject: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=4000)


class DoubtPatch(BaseModel):
    due_date: date | None = None
    priority: Literal["low","normal","high"] | None = None
    question: str | None = Field(default=None, min_length=3, max_length=2000)
    subject: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=4000)
    status: DoubtStatus | None = None


def _out(d: Doubt, title: str | None) -> dict:
    return {"id": d.id, "question": d.question, "note": d.note, "subject": d.subject, "status": d.status,
            "lecture_id": d.lecture_id, "lecture_title": title, "timestamp": d.timestamp,
            "due_date":d.due_date,"priority":d.priority,"history":d.history, "flashcard_id": d.flashcard_id, "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat()}


def _owned(db: Session, user: User, doubt_id: int) -> Doubt:
    d = db.get(Doubt, doubt_id)
    if d is None or d.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doubt not found")
    return d


def _title(db: Session, d: Doubt) -> str | None:
    return db.scalar(select(Lecture.title).where(Lecture.id == d.lecture_id)) if d.lecture_id else None


@router.post("", status_code=status.HTTP_201_CREATED)
def create(payload: DoubtIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.lecture_id is not None:
        get_owned_lecture(db, user, payload.lecture_id)  # 404 if not the student's lecture
    elif payload.timestamp is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A timestamp needs a lecture")
    data=payload.model_dump();data["due_date"]=payload.due_date.isoformat() if payload.due_date else None
    d = Doubt(user_id=user.id, **data)
    db.add(d)
    db.commit()
    return _out(d, _title(db, d))


@router.get("")
def list_doubts(status_filter: DoubtStatus | None = Query(default=None, alias="status"),
                subject: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stmt = select(Doubt).where(Doubt.user_id == user.id)
    if status_filter:
        stmt = stmt.where(Doubt.status == status_filter)
    if subject:
        stmt = stmt.where(Doubt.subject == subject)
    rows = db.scalars(stmt.order_by(Doubt.updated_at.desc())).all()
    titles = {t.id: t.title for t in db.scalars(select(Lecture).where(Lecture.user_id == user.id)).all()}
    allrows = db.scalars(select(Doubt).where(Doubt.user_id == user.id)).all()
    counts = {"unresolved": 0, "in_progress": 0, "resolved": 0}
    for r in allrows:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"items": [_out(r, titles.get(r.lecture_id)) for r in rows], "counts": counts,
            "subjects": sorted({r.subject for r in allrows if r.subject})}


@router.patch("/{doubt_id}")
def update(doubt_id: int, payload: DoubtPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    d = _owned(db, user, doubt_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        if k=="due_date":
            d.due_date=v.isoformat() if v else None
        elif v is not None:
            if k=="status" and v!=d.status:
                d.history=[*(d.history or []),{"from":d.status,"to":v,"at":datetime.now(timezone.utc).isoformat()}]
            setattr(d, k, v)
    db.commit()
    return _out(d, _title(db, d))


@router.delete("/{doubt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(doubt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_owned(db, user, doubt_id))
    db.commit()


@router.post("/{doubt_id}/flashcard", status_code=status.HTTP_201_CREATED)
def to_flashcard(doubt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Resolved doubt -> flashcard. The student's own resolution note becomes the answer; nothing is invented."""
    d = _owned(db, user, doubt_id)
    if d.status != "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Mark the doubt resolved first")
    if not d.note.strip():
        raise HTTPException(status.HTTP_409_CONFLICT, "Add your resolution to the notes first — it becomes the card's answer")
    if d.lecture_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Link this doubt to a lecture to turn it into a card")
    if d.flashcard_id and db.get(Flashcard, d.flashcard_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "This doubt already has a flashcard")
    card = Flashcard(user_id=user.id, lecture_id=d.lecture_id, topic=d.subject, front=d.question, back=d.note)
    db.add(card)
    db.flush()
    d.flashcard_id = card.id
    db.commit()
    return FlashcardOut.model_validate(card).model_dump(mode="json")
