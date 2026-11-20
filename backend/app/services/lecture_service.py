from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Bookmark, Chapter, Lecture, Topic, TopicMastery, TranscriptSegment, User
from . import transcript as transcript_svc
from .rag import retriever


def get_owned_lecture(db: Session, user: User, lecture_id: int) -> Lecture:
    lecture = db.get(Lecture, lecture_id)
    if lecture is None or lecture.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lecture not found")
    return lecture


def segment_tuples(lecture: Lecture) -> list[tuple[int, float, float, str]]:
    return [(s.id, s.start, s.end, s.text) for s in sorted(lecture.segments, key=lambda x: x.idx)]


def store_segments(
    db: Session,
    lecture: Lecture,
    segments: list[transcript_svc.ParsedSegment],
    source: str,
) -> None:
    """Replace transcript, then refresh derived chapters/topics."""
    db.execute(delete(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture.id))
    db.execute(delete(Chapter).where(Chapter.lecture_id == lecture.id))
    db.execute(delete(Topic).where(Topic.lecture_id == lecture.id))

    for idx, seg in enumerate(segments):
        db.add(
            TranscriptSegment(
                lecture_id=lecture.id,
                idx=idx,
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text=seg.text,
            )
        )
    lecture.transcript_status = "ready" if segments else "missing"
    lecture.source = source
    db.add(lecture)
    db.flush()
    refresh_derived(db, lecture)
    db.commit()
    retriever.invalidate(lecture.id)


def refresh_derived(db: Session, lecture: Lecture) -> None:
    segs = sorted(lecture.segments, key=lambda x: x.idx)
    parsed = [transcript_svc.ParsedSegment(s.start, s.end, s.text) for s in segs]

    for idx, (title, start) in enumerate(transcript_svc.build_chapters(parsed)):
        db.add(Chapter(lecture_id=lecture.id, idx=idx, title=title, start=round(start, 3)))

    existing = {t.name for t in lecture.topics}
    for phrase, _count in transcript_svc.keyphrases(parsed, limit=10):
        if phrase.lower() not in {e.lower() for e in existing}:
            db.add(Topic(lecture_id=lecture.id, name=phrase))
            existing.add(phrase)


def mastery_for(db: Session, user: User, topic: Topic) -> float | None:
    row = db.scalar(
        select(TopicMastery).where(
            TopicMastery.user_id == user.id, TopicMastery.topic_id == topic.id
        )
    )
    return round(row.score, 3) if row else None


def ensure_bookmark_access(db: Session, user: User, bookmark_id: int) -> Bookmark:
    bm = db.get(Bookmark, bookmark_id)
    if bm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bookmark not found")
    lecture = db.get(Lecture, bm.lecture_id)
    if lecture is None or lecture.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bookmark not found")
    return bm
