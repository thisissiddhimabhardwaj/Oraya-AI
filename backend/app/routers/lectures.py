from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..database import get_db
from ..deps import get_current_user
from ..models import Bookmark, Chapter, Lecture, Topic, TranscriptSegment, User
from ..schemas import (
    BookmarkCreate,
    BookmarkOut,
    ChapterOut,
    Items,
    LectureCreate,
    LectureDetail,
    LectureOut,
    SearchIn,
    SearchOut,
    SearchResult,
    SegmentOut,
    TopicList,
    TopicOut,
    TranscriptOut,
)
from ..services import lecture_service, transcript as transcript_svc
from ..services.youtube import InvalidURLError, canonical_url, extract_video_id, fetch_metadata, probe_duration

router = APIRouter(prefix="/lectures", tags=["lectures"])


# ---------------------------------------------------------------- create / read
@router.post("", response_model=LectureDetail, status_code=status.HTTP_201_CREATED)
async def create_lecture(
    payload: LectureCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LectureDetail:
    try:
        video_id = extract_video_id(payload.url)
    except InvalidURLError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    existing = db.scalar(
        select(Lecture).where(Lecture.user_id == user.id, Lecture.video_id == video_id)
    )
    if existing is not None:
        return _detail(db, user, existing)

    meta = await fetch_metadata(video_id)
    duration = await probe_duration(video_id)
    lecture = Lecture(
        user_id=user.id,
        video_id=video_id,
        url=canonical_url(video_id),
        title=(payload.title or meta["title"])[:512],
        channel=meta["channel"],
        thumbnail=meta["thumbnail"],
        duration=duration,
        transcript_status="missing",
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)

    # Attempt a live transcript fetch (optional dependency + network).
    fetched = await run_in_threadpool(transcript_svc.fetch_from_youtube, video_id)
    if fetched:
        lecture_service.store_segments(db, lecture, fetched, source="fetched")
        db.refresh(lecture)

    return _detail(db, user, lecture)


@router.get("", response_model=Items)
def list_lectures(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Items:
    rows = db.scalars(
        select(Lecture).where(Lecture.user_id == user.id).order_by(Lecture.created_at.desc())
    ).all()
    return Items(items=[LectureOut.model_validate(r) for r in rows])


def _detail(db: Session, user: User, lecture: Lecture) -> LectureDetail:
    detail = LectureDetail.model_validate(lecture)
    detail.chapters = [ChapterOut.model_validate(c) for c in sorted(lecture.chapters, key=lambda x: x.idx)]
    detail.bookmark_count = len(lecture.bookmarks)
    detail.topic_count = len(lecture.topics)
    detail.note_count = len(lecture.notes)
    return detail


@router.get("/{lecture_id}", response_model=LectureDetail)
def get_lecture(
    lecture_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LectureDetail:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    return _detail(db, user, lecture)


@router.delete("/{lecture_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lecture(
    lecture_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    db.delete(lecture)
    db.commit()


# ---------------------------------------------------------------- transcript
@router.get("/{lecture_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    lecture_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptOut:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    segs = sorted(lecture.segments, key=lambda x: x.idx)
    return TranscriptOut(
        lecture_id=lecture.id,
        source=lecture.source,
        timed=any(s.end > s.start for s in segs),
        segments=[SegmentOut.model_validate(s) for s in segs],
        chapters=[ChapterOut.model_validate(c) for c in sorted(lecture.chapters, key=lambda x: x.idx)],
    )


@router.post("/{lecture_id}/transcript", response_model=TranscriptOut)
async def upload_transcript(
    lecture_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptOut:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    if not file.filename or not file.filename.lower().endswith((".srt", ".vtt", ".txt")):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Upload an .srt, .vtt or .txt transcript file",
        )
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Transcript file is too large (2 MB max)")
    try:
        parsed = await run_in_threadpool(transcript_svc.parse_transcript_file, file.filename, raw)
    except transcript_svc.TranscriptError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    if len(parsed) > 20_000:
        parsed = parsed[:20_000]

    lecture_service.store_segments(db, lecture, parsed, source="upload")
    db.refresh(lecture)
    return await run_in_threadpool(get_transcript, lecture_id, user, db)


@router.post("/{lecture_id}/transcript/search", response_model=SearchOut)
def search_transcript(
    lecture_id: int,
    payload: SearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    from ..services.rag import retriever

    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    segs = lecture_service.segment_tuples(lecture)
    if not segs:
        return SearchOut(items=[])
    hits = retriever.retrieve(lecture.id, segs, payload.q, k=8)
    by_id = {s[0]: s for s in segs}
    items: list[SearchResult] = []
    for hit in hits:
        source = hit.quote_source or hit.passage
        if not source.segment_ids:
            continue
        sid = source.segment_ids[0]
        seg = by_id.get(sid)
        if seg is None:
            continue
        items.append(
            SearchResult(segment_id=sid, start=seg[1], end=seg[2], text=seg[3], score=hit.score)
        )
    return SearchOut(items=items)


# ---------------------------------------------------------------- topics / bookmarks
@router.get("/{lecture_id}/topics", response_model=TopicList)
def list_topics(
    lecture_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TopicList:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    items = [
        TopicOut(id=t.id, name=t.name, mastery=lecture_service.mastery_for(db, user, t))
        for t in lecture.topics
    ]
    return TopicList(items=items)


@router.get("/{lecture_id}/bookmarks", response_model=Items)
def list_bookmarks(
    lecture_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Items:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    return Items(items=[BookmarkOut.model_validate(b) for b in lecture.bookmarks])


@router.post("/{lecture_id}/bookmarks", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    lecture_id: int,
    payload: BookmarkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookmarkOut:
    lecture = lecture_service.get_owned_lecture(db, user, lecture_id)
    bm = Bookmark(lecture_id=lecture.id, ts=payload.ts, label=payload.label.strip())
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return BookmarkOut.model_validate(bm)


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    bm = lecture_service.ensure_bookmark_access(db, user, bookmark_id)
    db.delete(bm)
    db.commit()
