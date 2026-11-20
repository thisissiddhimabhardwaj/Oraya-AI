from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select,update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Lecture, User, VideoJob
from ..schemas import ExplainerCreate, Items, RendererInfo, VideoJobOut
from ..services.lecture_service import get_owned_lecture
from ..services.video_jobs import renderer_status
from ..services.video_jobs import enqueue,validate_mp4
from functools import lru_cache

@lru_cache(maxsize=256)
def _verified_media(path,mtime,size):
    validate_mp4(Path(path))
    return True

router = APIRouter(tags=["videos"])


def _job_out(job: VideoJob) -> VideoJobOut:
    status_val = job.status
    video_url = None
    validation_error=None
    if status_val=="completed":
        try:
            media=Path(job.video_path).resolve()
            if not media.is_relative_to(Path(settings.storage_dir).resolve()):raise ValueError('Video is outside private storage')
            stat=media.stat();_verified_media(str(media),stat.st_mtime_ns,stat.st_size)
            video_url=f"/video-jobs/{job.id}/download?kind=mp4"
        except Exception:
            status_val='failed';validation_error='The video is missing or has not passed narrated-MP4 validation. Retry rendering.'
    return VideoJobOut(
        id=job.id,
        lecture_id=job.lecture_id,
        concept=job.concept,
        complexity=job.complexity,
        status=status_val,
        script_mode=(job.scene_plan or {}).get("generation_mode"),
        stage=job.stage,
        progress=job.progress,
        scene_plan=job.scene_plan,
        script=job.script,
        narration=job.narration,
        video_url=video_url,
        renderer=RendererInfo(**renderer_status()),
        error=validation_error or job.error or None,
        created_at=job.created_at,
    )


@router.post(
    "/lectures/{lecture_id}/explainer-videos",
    response_model=VideoJobOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_explainer(
    lecture_id: int,
    payload: ExplainerCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobOut:
    lecture = get_owned_lecture(db, user, lecture_id)
    if not lecture.segments:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lecture has no transcript yet")

    existing = db.scalars(select(VideoJob).where(VideoJob.user_id==user.id, VideoJob.lecture_id==lecture.id, VideoJob.concept==payload.concept.strip(), VideoJob.complexity==payload.complexity, VideoJob.status.not_in(["failed","completed","render_skipped"]))).first()
    if existing:return _job_out(existing)
    job = VideoJob(
        lecture_id=lecture.id,
        user_id=user.id,
        concept=payload.concept.strip(),
        complexity=payload.complexity,
        script={"source_excerpt":True} if payload.source_excerpt else None,
        status="queued",
        stage="Waiting to start",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue(job.id)
    return _job_out(job)


@router.get("/video-jobs", response_model=Items)
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Items:
    rows = db.scalars(
        select(VideoJob).where(VideoJob.user_id == user.id).order_by(VideoJob.created_at.desc())
    ).all()
    return Items(items=[_job_out(j) for j in rows])


def _job_or_404(db: Session, user: User, job_id: int) -> VideoJob:
    job = db.get(VideoJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("/video-jobs/{job_id}", response_model=VideoJobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobOut:
    return _job_out(_job_or_404(db, user, job_id))


_KINDS = {
    "mp4": ("explainer.mp4", "video/mp4"),
    "audio-status": ("narration-status.json", "application/json"),
    "srt": ("subtitles.srt", "text/plain; charset=utf-8"),
    "py": ("scene.py", "text/x-python"),
    "script": ("script.json", "application/json"),
    "plan": ("plan.json", "application/json"),
    "narration": ("narration.txt", "text/plain; charset=utf-8"),
}


@router.get("/video-jobs/{job_id}/download")
def download(
    job_id: int,
    kind: str = "mp4",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = _job_or_404(db, user, job_id)
    if kind not in _KINDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"kind must be one of {', '.join(_KINDS)}",
        )
    filename, media_type = _KINDS[kind]
    path = Path(job.video_path) if (kind == "mp4" and job.video_path) else None
    if path is None:
        path = Path(settings.storage_dir) / "jobs" / str(job.id) / filename
    if not path.resolve().is_relative_to(Path(settings.storage_dir).resolve()):
        raise HTTPException(403,"Artifact is outside the private storage directory")
    if kind=="mp4":
        if job.status!="completed":raise HTTPException(409,"The video is not complete")
        try:
            stat=path.stat();_verified_media(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
        except Exception:raise HTTPException(409,"The video has not passed validation")
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {kind} artifact for this job yet")
    return FileResponse(path, media_type=media_type, filename=f"oraya-{job.concept[:40] or 'explainer'}-{filename}")


@router.get("/renderer-status", response_model=RendererInfo)
def renderer_info() -> RendererInfo:
    return RendererInfo(**renderer_status())


@router.post('/video-jobs/{job_id}/retry',response_model=VideoJobOut,status_code=202)
async def retry_job(job_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    job=_job_or_404(db,user,job_id)
    if job.status not in ('failed','render_skipped','completed'):raise HTTPException(409,'This job is already in progress')
    if job.status=='completed' and _job_out(job).status=='completed':raise HTTPException(409,'This video is already complete')
    changed=db.execute(update(VideoJob).where(VideoJob.id==job.id,VideoJob.status.in_(['failed','render_skipped','completed'])).values(status='queued',error='',progress=0,stage='Waiting to retry',video_path='').execution_options(synchronize_session=False))
    db.commit()
    if not changed.rowcount:raise HTTPException(409,'A retry is already in progress')
    db.refresh(job);enqueue(job.id);return _job_out(job)
