from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Difficulty = Literal["easy", "medium", "hard", "mixed"]
NoteKind = Literal["summary", "chapters", "definitions", "manual"]
Complexity = Literal["beginner", "intermediate", "advanced"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator('*',mode='after')
    @classmethod
    def _utc_dates(cls,value):
        if isinstance(value,datetime) and value.tzinfo is None:return value.replace(tzinfo=timezone.utc)
        return value


# ---------------------------------------------------------------- auth
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    grade: str
    language: str
    subjects: list[str]
    prefs: dict = {}
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    grade: str | None = Field(default=None, max_length=20)
    language: str | None = Field(default=None, max_length=40)
    subjects: list[str] | None = None
    prefs: dict | None = None


# ---------------------------------------------------------------- lectures
class LectureCreate(BaseModel):
    url: str = Field(min_length=8, max_length=512)
    title: str | None = Field(default=None, max_length=512)


class LectureOut(ORMModel):
    id: int
    video_id: str
    url: str
    title: str
    channel: str
    thumbnail: str
    duration: int
    source: str
    transcript_status: str
    created_at: datetime


class LectureDetail(LectureOut):
    chapters: list["ChapterOut"] = []
    bookmark_count: int = 0
    topic_count: int = 0
    note_count: int = 0


class ChapterOut(ORMModel):
    id: int
    idx: int
    title: str
    start: float


class SegmentOut(ORMModel):
    id: int
    idx: int
    start: float
    end: float
    text: str


class TranscriptOut(BaseModel):
    lecture_id: int
    source: str
    timed: bool = True
    segments: list[SegmentOut]
    chapters: list[ChapterOut]


class SearchIn(BaseModel):
    q: str = Field(min_length=1, max_length=200)


class SearchResult(BaseModel):
    segment_id: int
    start: float
    end: float
    text: str
    score: float


class SearchOut(BaseModel):
    items: list[SearchResult]


class TopicOut(BaseModel):
    id: int
    name: str
    mastery: float | None = None


class TopicList(BaseModel):
    items: list[TopicOut]


class BookmarkCreate(BaseModel):
    ts: float = Field(ge=0)
    label: str = Field(default="", max_length=255)


class BookmarkOut(ORMModel):
    id: int
    ts: float
    label: str


class Items(BaseModel):
    items: list[Any]


# ---------------------------------------------------------------- tutor
class TutorAsk(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class Reference(BaseModel):
    segment_id: int | None = None
    start: float
    end: float
    quote: str


class TutorAnswer(BaseModel):
    answer: str
    mode: str
    references: list[Reference] = []
    notice: str | None = None


class Suggestions(BaseModel):
    items: list[str]


# ---------------------------------------------------------------- notes
class NoteGenerate(BaseModel):
    kind: NoteKind = "summary"


class NoteOut(ORMModel):
    id: int
    lecture_id: int
    kind: str
    title: str
    content_md: str
    mode: str
    created_at: datetime


class NotePatch(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    content_md: str | None = Field(default=None, max_length=200_000)


# ---------------------------------------------------------------- quiz
class QuizGenerate(BaseModel):
    count: int = Field(default=5, ge=3, le=20)
    difficulty: Difficulty = "mixed"
    topics: list[str] = Field(default_factory=list, max_length=20)


class QuestionOut(BaseModel):
    id: int
    idx: int
    type: str
    prompt: str
    options: list[str] | None = None
    topic: str
    difficulty: str


class QuizOut(BaseModel):
    id: int
    lecture_id: int
    lecture_title: str = ""
    mode: str
    config: dict
    questions: list[QuestionOut]
    created_at: datetime


class AnswerIn(BaseModel):
    question_id: int
    answer: str = Field(max_length=2000)


class AttemptIn(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1, max_length=50)


class QuestionResult(BaseModel):
    question_id: int
    correct: bool
    correct_answer: str
    explanation: str
    topic: str


class AttemptOut(BaseModel):
    attempt_id: int
    score: float
    count: int
    results: list[QuestionResult]
    gaps: list[str]


class HistoryItem(BaseModel):
    id: int
    lecture_id: int
    lecture_title: str
    score: float
    count: int
    created_at: datetime


# ---------------------------------------------------------------- progress
class MasteryItem(BaseModel):
    topic: str
    score: float
    lecture_count: int


class Recommendation(BaseModel):
    type: str
    label: str
    href: str


class ProgressOverview(BaseModel):
    mastery: list[MasteryItem]
    weak_topics: list[str]
    recommendations: list[Recommendation]
    streak_days: int
    totals: dict
    mode: str


class FlashcardOut(ORMModel):
    id: int
    lecture_id: int
    topic: str
    front: str
    back: str
    interval_days: float
    due_at: datetime

    @field_validator("due_at")
    @classmethod
    def due_date_is_utc(cls, value: datetime) -> datetime:
        # SQLite returns naive timestamps even though the scheduler stores UTC.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class FlashcardReview(BaseModel):
    quality: int = Field(ge=0, le=3)


# ---------------------------------------------------------------- video jobs
class ExplainerCreate(BaseModel):
    source_excerpt: bool = False
    concept: str = Field(min_length=2, max_length=255)
    complexity: Complexity = "intermediate"


class RendererInfo(BaseModel):
    manim: bool
    ffmpeg: bool
    ffprobe: bool = False
    tts: bool = False
    tts_provider: str = ""
    renderer: str = ""
    supported: bool = False


class VideoJobOut(BaseModel):
    id: int
    lecture_id: int
    concept: str
    complexity: str
    status: str
    script_mode: str | None = None
    stage: str
    progress: int
    scene_plan: dict | None = None
    script: dict | None = None
    narration: str = ""
    video_url: str | None = None
    renderer: RendererInfo
    error: str | None = None
    created_at: datetime


# ---------------------------------------------------------------- dashboard
class DashboardStats(BaseModel):
    lectures: int = 0
    notes: int = 0
    quizzes: int = 0
    videos: int = 0
    avg_score: float = 0.0
    minutes_watched: int = 0


class ActivityDay(BaseModel):
    date: str
    items: int


class DashboardOut(BaseModel):
    stats: DashboardStats
    recent_lectures: list[LectureOut]
    recent_attempts: list[HistoryItem]
    activity: list[ActivityDay]
    mode: str
