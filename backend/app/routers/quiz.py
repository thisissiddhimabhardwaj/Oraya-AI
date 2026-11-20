from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Lecture, Quiz, QuizAttempt, QuizQuestion, Topic, TopicMastery, User
from ..schemas import (
    AttemptIn,
    AttemptOut,
    HistoryItem,
    Items,
    QuestionOut,
    QuestionResult,
    QuizGenerate,
    QuizOut,
)
from ..services import demo_ai
from ..services.ai import ai
from ..services.lecture_service import get_owned_lecture, segment_tuples

router = APIRouter(tags=["quiz"])

QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["mcq", "short"]},
                    "prompt": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "answer": {"type": "string"},
                    "explanation": {"type": "string"},
                    "topic": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                },
                "required": ["type", "prompt", "answer", "explanation"],
            },
        }
    },
    "required": ["questions"],
}


def _clean_question(raw: dict, idx: int, fallback_topic: str) -> QuizQuestion | None:
    qtype = str(raw.get("type", "mcq")).lower()
    qtype = "mcq" if qtype in ("mcq", "multiple", "multiple_choice") else "short"
    prompt = re.sub(r"\s+", " ", str(raw.get("prompt", ""))).strip()[:1000]
    answer = str(raw.get("answer", "")).strip()[:2000]
    if not prompt or not answer:
        return None
    options = raw.get("options") if qtype == "mcq" else None
    if qtype == "mcq":
        if not isinstance(options, list):
            return None
        options = [str(o).strip()[:300] for o in options if str(o).strip()]
        if len(options) < 2 or answer not in options:
            if len(options) >= 2 and answer not in options:
                options = options[:3] + [answer]
            elif len(options) < 2:
                return None
        options = options[:6]
    else:
        options = None
    difficulty = str(raw.get("difficulty", "medium")).lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    return QuizQuestion(
        idx=idx,
        type=qtype,
        prompt=prompt,
        options=options,
        answer=answer,
        explanation=re.sub(r"\s+", " ", str(raw.get("explanation", ""))).strip()[:600],
        topic=(str(raw.get("topic", "")).strip()[:120] or fallback_topic),
        difficulty=difficulty,
    )


@router.post("/lectures/{lecture_id}/quiz/generate", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    lecture_id: int,
    payload: QuizGenerate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizOut:
    lecture = get_owned_lecture(db, user, lecture_id)
    segs = segment_tuples(lecture)
    if not segs:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lecture has no transcript yet")
    if sum(len(s[3]) for s in segs) < 100:
        raise HTTPException(status.HTTP_409_CONFLICT, "Transcript is too short to quiz you on")

    chapters = [(c.title, c.start) for c in sorted(lecture.chapters, key=lambda x: x.idx)]
    fallback_topic = chapters[0][0] if chapters else "General"

    transcript_block = "\n".join(f"[{s[1]:.0f}s] {s[3]}" for s in segs[:300])
    topic_hint = f"Focus topics: {', '.join(payload.topics)}." if payload.topics else ""
    prompt = (
        f"Create {payload.count} quiz questions for this lecture (difficulty: {payload.difficulty}). "
        f"{topic_hint}\n"
        "Mix multiple choice (4 options, exactly one correct) and short answer. "
        "Every question must be answerable strictly from the transcript; "
        "the explanation must quote the transcript.\n\n"
        f"Transcript:\n{transcript_block}"
    )

    def fallback() -> dict:
        return demo_ai.generate_quiz(
            lecture.title, segs, chapters, payload.count,
            payload.difficulty, payload.topics,
        )

    data, mode = ai.complete_json(
        prompt,
        QUIZ_SCHEMA,
        system="You write fair, unambiguous quiz questions grounded in the supplied transcript.",
        fallback=fallback,
    )

    raw_questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(raw_questions, list):
        from ..config import settings
        if not settings.allow_demo_ai:
            from ..services.ai import AIError
            raise AIError("AI returned an invalid quiz. Please retry.")
        raw_questions = fallback()["questions"]
        mode = "demo"

    quiz = Quiz(
        lecture_id=lecture.id,
        config={"count": payload.count, "difficulty": payload.difficulty, "topics": payload.topics},
        mode=mode,
    )
    db.add(quiz)
    db.flush()

    added = 0
    for raw in raw_questions:
        if not isinstance(raw, dict):
            continue
        q = _clean_question(raw, added, fallback_topic)
        if q is None:
            continue
        q.quiz_id = quiz.id
        db.add(q)
        added += 1
        if added >= payload.count:
            break

    if added == 0:
        db.rollback()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Could not build quiz questions from this transcript — try again or upload a fuller transcript.",
        )

    db.commit()
    db.refresh(quiz)
    return _quiz_out(db, quiz)


def _quiz_out(db: Session, quiz: Quiz) -> QuizOut:
    lecture = db.get(Lecture, quiz.lecture_id)
    return QuizOut(
        id=quiz.id,
        lecture_id=quiz.lecture_id,
        lecture_title=lecture.title if lecture else "",
        mode=quiz.mode,
        config=quiz.config or {},
        questions=[
            QuestionOut(
                id=q.id,
                idx=q.idx,
                type=q.type,
                prompt=q.prompt,
                options=q.options,
                topic=q.topic,
                difficulty=q.difficulty,
            )
            for q in sorted(quiz.questions, key=lambda x: x.idx)
        ],
        created_at=quiz.created_at,
    )


def _quiz_or_404(db: Session, user: User, quiz_id: int) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    lecture = db.get(Lecture, quiz.lecture_id) if quiz else None
    if quiz is None or lecture is None or lecture.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    return quiz


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
def get_quiz(
    quiz_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizOut:
    return _quiz_out(db, _quiz_or_404(db, user, quiz_id))


@router.post("/quizzes/{quiz_id}/attempts", response_model=AttemptOut)
def submit_attempt(
    quiz_id: int,
    payload: AttemptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttemptOut:
    quiz = _quiz_or_404(db, user, quiz_id)
    given = {a.question_id: a.answer.strip() for a in payload.answers}

    results: list[QuestionResult] = []
    topic_scores: dict[str, list[int]] = {}
    correct_count = 0
    questions = sorted(quiz.questions, key=lambda x: x.idx)

    for q in questions:
        ans = given.get(q.id, "")
        if q.type == "mcq":
            ok = _norm(ans) == _norm(q.answer)
        else:
            ok = demo_ai.grade_short(ans, q.answer) if ans else False
        correct_count += 1 if ok else 0
        topic_scores.setdefault(q.topic, []).append(1 if ok else 0)
        results.append(
            QuestionResult(
                question_id=q.id,
                correct=ok,
                correct_answer=q.answer,
                explanation=q.explanation,
                topic=q.topic,
            )
        )

    if not results:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No answers submitted")

    score = round(correct_count / len(results), 3)
    gaps = sorted(
        [t for t, vals in topic_scores.items() if sum(vals) / len(vals) < 0.6],
        key=lambda t: sum(topic_scores[t]) / len(topic_scores[t]),
    )

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user.id,
        score=score,
        count=len(results),
        results=[r.model_dump() for r in results],
        gaps=gaps,
    )
    db.add(attempt)

    # persist mastery per topic
    for topic_name, vals in topic_scores.items():
        ratio = sum(vals) / len(vals)
        topic = db.scalar(select(Topic).where(Topic.lecture_id == quiz.lecture_id, Topic.name == topic_name))
        if topic is None:
            topic = Topic(lecture_id=quiz.lecture_id, name=topic_name)
            db.add(topic)
            db.flush()
        row = db.scalar(
            select(TopicMastery).where(TopicMastery.user_id == user.id, TopicMastery.topic_id == topic.id)
        )
        if row is None:
            row = TopicMastery(user_id=user.id, topic_id=topic.id, score=ratio)
        else:
            row.score = round(0.6 * row.score + 0.4 * ratio, 3)
        db.add(row)

    db.commit()
    db.refresh(attempt)
    return AttemptOut(
        attempt_id=attempt.id,
        score=attempt.score,
        count=attempt.count,
        results=results,
        gaps=gaps,
    )


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


@router.get("/quiz-history", response_model=Items)
def quiz_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Items:
    rows = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(30)
    ).all()
    items = []
    for a in rows:
        quiz = db.get(Quiz, a.quiz_id)
        lecture = db.get(Lecture, quiz.lecture_id) if quiz else None
        items.append(
            HistoryItem(
                id=a.id,
                lecture_id=lecture.id if lecture else 0,
                lecture_title=lecture.title if lecture else "Lecture",
                score=a.score,
                count=a.count,
                created_at=a.created_at,
            )
        )
    return Items(items=items)
