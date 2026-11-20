"""Smart Revision Engine — queue + analytics over the persisted review log."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Flashcard, ReviewLog, User
from ..schemas import FlashcardOut
from ..services.srs import maturity

router = APIRouter(prefix="/revision", tags=["revision"])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/queue")
def queue(limit: int = Query(default=20, ge=1, le=100), user: User = Depends(get_current_user),
          db: Session = Depends(get_db)) -> dict:
    """Today's queue: overdue cards first (most overdue at the top), then anything due now."""
    now = datetime.now(timezone.utc)
    due = db.scalars(
        select(Flashcard).where(Flashcard.user_id == user.id, Flashcard.due_at <= now).order_by(Flashcard.due_at)
    ).all()
    return {"total_due": len(due), "items": [FlashcardOut.model_validate(c).model_dump(mode="json") for c in due[:limit]]}


@router.get("/analytics")
def analytics(days: int = Query(default=14, ge=7, le=90), user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    logs = db.scalars(select(ReviewLog).where(ReviewLog.user_id == user.id, ReviewLog.created_at >= since)).all()
    cards = db.scalars(select(Flashcard).where(Flashcard.user_id == user.id)).all()

    per_day: dict[str, dict] = {}
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date().isoformat()
        per_day[d] = {"date": d, "reviews": 0, "correct": 0}
    topic_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # topic -> [reviews, lapses]
    card_topic = {c.id: (c.topic or "General") for c in cards}
    for log in logs:
        key = _aware(log.created_at).date().isoformat()
        if key in per_day:
            per_day[key]["reviews"] += 1
            per_day[key]["correct"] += 1 if log.quality >= 2 else 0
        t = topic_stats[card_topic.get(log.flashcard_id, "General")]
        t[0] += 1
        t[1] += 1 if log.quality < 2 else 0

    stages = {"new": 0, "learning": 0, "young": 0, "mature": 0}
    for c in cards:
        stages[maturity(c.reps, c.interval_days)] += 1

    # Weak-topic detection: need >=3 reviews so one slip doesn't flag a topic.
    weak = sorted(
        ({"topic": t, "reviews": r, "lapses": l, "recall_rate": round(1 - l / r, 3)}
         for t, (r, l) in topic_stats.items() if r >= 3 and l / r >= 0.3),
        key=lambda x: x["recall_rate"],
    )
    total = len(logs)
    correct = sum(1 for l in logs if l.quality >= 2)
    streak, day = 0, now.date()
    active = {k for k, v in per_day.items() if v["reviews"]}
    if day.isoformat() not in active:
        day -= timedelta(days=1)
    while day.isoformat() in active:
        streak += 1
        day -= timedelta(days=1)
    return {
        "window_days": days, "total_reviews": total,
        "retention": round(correct / total, 3) if total else None,
        "review_streak": streak, "by_day": list(per_day.values()),
        "stages": stages, "weak_topics": weak, "cards_total": len(cards),
        "due_now": sum(1 for c in cards if _aware(c.due_at) <= now),
    }
