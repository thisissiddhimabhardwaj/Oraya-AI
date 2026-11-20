from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    name: Mapped[str] = mapped_column(String(120), default="")
    grade: Mapped[str] = mapped_column(String(20), default="")
    language: Mapped[str] = mapped_column(String(40), default="English")
    subjects: Mapped[list] = mapped_column(JSON, default=list)
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lectures: Mapped[list["Lecture"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[str] = mapped_column(String(24), index=True)
    url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String(512), default="Untitled lecture")
    channel: Mapped[str] = mapped_column(String(255), default="")
    thumbnail: Mapped[str] = mapped_column(String(512), default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="fetched")  # fetched|upload|sample
    transcript_status: Mapped[str] = mapped_column(String(16), default="missing")  # ready|missing
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="lectures")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan", order_by="TranscriptSegment.idx"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan", order_by="Chapter.idx"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan", order_by="Bookmark.ts"
    )
    notes: Mapped[list["Note"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    quizzes: Mapped[list["Quiz"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    topics: Mapped[list["Topic"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    video_jobs: Mapped[list["VideoJob"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    tutor_messages: Mapped[list["TutorMessage"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer, default=0)
    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    text: Mapped[str] = mapped_column(Text, default="")

    lecture: Mapped[Lecture] = relationship(back_populates="segments")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255), default="")
    start: Mapped[float] = mapped_column(Float, default=0.0)

    lecture: Mapped[Lecture] = relationship(back_populates="chapters")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    ts: Mapped[float] = mapped_column(Float, default=0.0)
    label: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped[Lecture] = relationship(back_populates="bookmarks")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="summary")
    title: Mapped[str] = mapped_column(String(512), default="Notes")
    content_md: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    lecture: Mapped[Lecture] = relationship(back_populates="notes")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(16), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped[Lecture] = relationship(back_populates="quizzes")
    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.idx"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(8), default="mcq")  # mcq|short
    prompt: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(120), default="")
    difficulty: Mapped[str] = mapped_column(String(12), default="medium")

    quiz: Mapped[Quiz] = relationship(back_populates="questions")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    count: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    quiz: Mapped[Quiz] = relationship(back_populates="attempts")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)

    lecture: Mapped[Lecture] = relationship(back_populates="topics")
    mastery: Mapped[list["TopicMastery"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    topic: Mapped[Topic] = relationship(back_populates="mastery")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(120), default="")
    front: Mapped[str] = mapped_column(Text, default="")
    back: Mapped[str] = mapped_column(Text, default="")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped[Lecture] = relationship(back_populates="flashcards")


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    concept: Mapped[str] = mapped_column(String(255), default="")
    complexity: Mapped[str] = mapped_column(String(16), default="intermediate")
    status: Mapped[str] = mapped_column(String(24), default="queued")
    stage: Mapped[str] = mapped_column(String(80), default="Waiting to start")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    scene_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    manim_source: Mapped[str] = mapped_column(Text, default="")
    narration: Mapped[str] = mapped_column(Text, default="")
    video_path: Mapped[str] = mapped_column(String(512), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped[Lecture] = relationship(back_populates="video_jobs")


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="user")  # user|assistant
    content: Mapped[str] = mapped_column(Text, default="")
    refs: Mapped[list] = mapped_column(JSON, default=list)
    mode: Mapped[str] = mapped_column(String(16), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped[Lecture] = relationship(back_populates="tutor_messages")


class WatchProgress(Base):
    __tablename__ = "watch_progress"

    __table_args__ = (__import__("sqlalchemy").UniqueConstraint("user_id", "lecture_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lecture_id: Mapped[int] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True
    )
    resume_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    seconds: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------ Phase 2/3 additions
# Additive tables only (created by Base.metadata.create_all); no existing table is altered.
class ReviewLog(Base):
    """One row per flashcard review — the audit trail behind spaced-repetition analytics."""

    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcards.id", ondelete="CASCADE"), index=True)
    quality: Mapped[int] = mapped_column(Integer)  # 0 again · 1 hard · 2 good · 3 easy
    interval_before: Mapped[float] = mapped_column(Float, default=0.0)
    interval_after: Mapped[float] = mapped_column(Float, default=0.0)
    ease_after: Mapped[float] = mapped_column(Float, default=2.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Doubt(Base):
    __tablename__ = "doubts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lecture_id: Mapped[int | None] = mapped_column(ForeignKey("lectures.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(String(120), default="")
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")
    history: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="unresolved")  # unresolved|in_progress|resolved
    flashcard_id: Mapped[int | None] = mapped_column(ForeignKey("flashcards.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    exam_date: Mapped[str] = mapped_column(String(10))  # ISO date
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60)
    lecture_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tasks: Mapped[list["StudyTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="StudyTask.day"
    )


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("study_plans.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)  # ISO date
    kind: Mapped[str] = mapped_column(String(16))  # watch|revise|practice
    title: Mapped[str] = mapped_column(String(255))
    lecture_id: Mapped[int | None] = mapped_column(ForeignKey("lectures.id", ondelete="SET NULL"), nullable=True)
    topic: Mapped[str] = mapped_column(String(120), default="")
    minutes: Mapped[int] = mapped_column(Integer, default=20)
    reason: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|done|missed
    rescheduled: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[StudyPlan] = relationship(back_populates="tasks")


class ExamSession(Base):
    __tablename__ = 'exam_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(160))
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    marked: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    results: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)


class StudyRoom(Base):
    __tablename__ = 'study_rooms'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    invite_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoomMember(Base):
    __tablename__ = 'room_members'
    __table_args__ = (__import__('sqlalchemy').UniqueConstraint('room_id', 'user_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey('study_rooms.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)


class RoomEntry(Base):
    __tablename__ = 'room_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey('study_rooms.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(16), default='note')
    content: Mapped[str] = mapped_column(Text)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningRecord(Base):
    __tablename__ = 'learning_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RevokedToken(Base):
    __tablename__ = 'revoked_tokens'
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SpatialEnvironment(Base):
    __tablename__ = 'spatial_environments'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    lecture_id: Mapped[int | None] = mapped_column(ForeignKey('lectures.id',ondelete='SET NULL'),nullable=True)
    topic: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200),default='New learning environment')
    spec: Mapped[dict] = mapped_column(JSON,default=dict)
    status: Mapped[str] = mapped_column(String(24),default='queued')
    error: Mapped[str] = mapped_column(Text,default='')
    progress: Mapped[dict] = mapped_column(JSON,default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)


class SpatialResponse(Base):
    __tablename__='spatial_responses'
    __table_args__=(__import__('sqlalchemy').UniqueConstraint('environment_id','user_id','submission_id'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    environment_id: Mapped[int]=mapped_column(ForeignKey('spatial_environments.id',ondelete='CASCADE'),index=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    submission_id: Mapped[str]=mapped_column(String(64))
    challenge_id: Mapped[str]=mapped_column(String(64))
    answer: Mapped[list]=mapped_column(JSON,default=list)
    correct: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class RevisionSession(Base):
    __tablename__='revision_sessions'
    __table_args__=(__import__('sqlalchemy').Index('uq_active_revision_user','user_id',unique=True,sqlite_where=__import__('sqlalchemy').text("status='active'")),)
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    card_ids: Mapped[list]=mapped_column(JSON,default=list)
    cursor: Mapped[int]=mapped_column(Integer,default=0)
    answers: Mapped[dict]=mapped_column(JSON,default=dict)
    status: Mapped[str]=mapped_column(String(16),default='active')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class RevisionResponse(Base):
    __tablename__='revision_responses'
    __table_args__=(__import__('sqlalchemy').UniqueConstraint('session_id','card_id'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    session_id: Mapped[int]=mapped_column(ForeignKey('revision_sessions.id',ondelete='CASCADE'),index=True)
    card_id: Mapped[int]=mapped_column(Integer)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    answer: Mapped[str]=mapped_column(Text,default='')
    quality: Mapped[int]=mapped_column(Integer)
    next_due: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
