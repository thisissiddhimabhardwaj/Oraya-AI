from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zoneinfo import ZoneInfo
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Lecture, Note, Quiz, QuizAttempt, User, VideoJob, WatchProgress
from ..schemas import ActivityDay, DashboardOut, DashboardStats, HistoryItem, LectureOut
from ..services.ai import ai

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOut:
    lectures = db.scalars(
        select(Lecture).where(Lecture.user_id == user.id).order_by(Lecture.created_at.desc())
    ).all()

    notes_count = db.scalar(
        select(func.count())
        .select_from(Note)
        .join(Lecture, Lecture.id == Note.lecture_id)
        .where(Lecture.user_id == user.id)
    ) or 0

    attempts = db.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id).order_by(QuizAttempt.created_at.desc())
    ).all()

    videos_count = db.scalar(
        select(func.count()).select_from(VideoJob).where(VideoJob.user_id == user.id)
    ) or 0

    seconds = db.scalar(
        select(func.coalesce(func.sum(WatchProgress.seconds), 0)).where(WatchProgress.user_id == user.id)
    ) or 0

    recent_attempts: list[HistoryItem] = []
    for a in attempts[:6]:
        quiz = db.get(Quiz, a.quiz_id)
        lecture = db.get(Lecture, quiz.lecture_id) if quiz else None
        recent_attempts.append(
            HistoryItem(
                id=a.id,
                lecture_id=lecture.id if lecture else 0,
                lecture_title=lecture.title if lecture else "Lecture",
                score=a.score,
                count=a.count,
                created_at=a.created_at,
            )
        )

    # activity over the last 14 days (real recorded events only)
    zone = ZoneInfo(settings.study_timezone)
    start = datetime.now(zone).date() - timedelta(days=13)
    counts: dict[str, int] = {}
    for day in range(14):
        counts[(start + timedelta(days=day)).isoformat()] = 0
    for a in attempts:
        key = (a.created_at.replace(tzinfo=timezone.utc) if a.created_at.tzinfo is None else a.created_at).astimezone(zone).date().isoformat()
        if key in counts:
            counts[key] += 1
    for lec in lectures:
        key = (lec.created_at.replace(tzinfo=timezone.utc) if lec.created_at.tzinfo is None else lec.created_at).astimezone(zone).date().isoformat()
        if key in counts:
            counts[key] += 1

    return DashboardOut(
        stats=DashboardStats(
            lectures=len(lectures),
            notes=notes_count,
            quizzes=len(attempts),
            videos=videos_count,
            avg_score=round(sum(a.score for a in attempts) / len(attempts), 3) if attempts else 0.0,
            minutes_watched=int(seconds // 60),
        ),
        recent_lectures=[LectureOut.model_validate(l) for l in lectures[:6]],
        recent_attempts=recent_attempts,
        activity=[ActivityDay(date=d, items=n) for d, n in sorted(counts.items())],
        mode=ai.mode,
    )
