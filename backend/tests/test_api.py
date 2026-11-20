"""API test suite (runs against SQLite in a temp dir, demo mode — no network needed).

Run:  python -m pytest -q
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = tempfile.mkdtemp(prefix="oraya-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["STORAGE_DIR"] = f"{_TMP}/storage"
os.environ["ALLOW_DEMO_AI"] = "true"
os.environ["SEED_DEMO"] = "true"
os.environ["GEMINI_API_KEY"] = ""  # force demo mode

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_data  # noqa: E402
from app.services.transcript import parse_srt, parse_transcript_file  # noqa: E402
from app.services.youtube import InvalidURLError, extract_video_id  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client: TestClient) -> dict:
    """All feature tests run as the seeded demo account (owns the sample lecture)."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_signup_login_roundtrip(client: TestClient) -> None:
    created = client.post(
        "/api/v1/auth/signup",
        json={"email": "tester@example.com", "password": "secret123", "name": "Tester"},
    )
    assert created.status_code == 201, created.text
    token = created.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "tester@example.com"

    # duplicate signup is rejected
    dup = client.post(
        "/api/v1/auth/signup",
        json={"email": "tester@example.com", "password": "secret123", "name": "Tester"},
    )
    assert dup.status_code == 409


# ---------------------------------------------------------------- auth
def test_signup_validation_rejects_weak_password(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": "weak@example.com", "password": "allletters", "name": "W"},
    )
    assert resp.status_code == 422


def test_login_and_me(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == DEMO_EMAIL


def test_bad_login_is_401(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": "nope12345"})
    assert resp.status_code == 401


def test_profile_update(client: TestClient, auth_headers: dict) -> None:
    resp = client.patch(
        "/api/v1/auth/profile",
        json={"grade": "Grade 10", "subjects": ["Physics", "Mathematics"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["grade"] == "Grade 10"
    assert resp.json()["subjects"] == ["Physics", "Mathematics"]


# ---------------------------------------------------------------- youtube helpers
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id(url: str, expected: str) -> None:
    assert extract_video_id(url) == expected


def test_extract_video_id_rejects_garbage() -> None:
    with pytest.raises(InvalidURLError):
        extract_video_id("https://example.com/not-a-video")


# ---------------------------------------------------------------- transcript parsing
def test_parse_srt() -> None:
    srt = "1\n00:00:01,000 --> 00:00:03,500\nHello world\n\n2\n00:00:04,000 --> 00:00:06,000\nSecond cue\n"
    segs = parse_srt(srt)
    assert len(segs) == 2
    assert segs[0].start == 1.0 and segs[0].end == 3.5
    assert segs[1].text == "Second cue"


def test_parse_vtt_and_plain() -> None:
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nCue one\n"
    assert parse_transcript_file("a.vtt", vtt.encode())[0].text == "Cue one"
    txt = "[01:10] Timed line\nUntimed line"
    segs = parse_transcript_file("a.txt", txt.encode())
    assert segs[0].start == 70.0
    assert segs[1].start == 0.0  # no invented timestamps


# ---------------------------------------------------------------- lectures
def test_create_lecture_rejects_bad_url(client: TestClient, auth_headers: dict) -> None:
    resp = client.post("/api/v1/lectures", json={"url": "https://example.com"}, headers=auth_headers)
    assert resp.status_code == 422


def test_sample_lecture_transcript_and_search(client: TestClient, auth_headers: dict) -> None:
    items = client.get("/api/v1/lectures", headers=auth_headers).json()["items"]
    sample = next(l for l in items if l["source"] == "sample")

    detail = client.get(f"/api/v1/lectures/{sample['id']}", headers=auth_headers).json()
    assert detail["transcript_status"] == "ready"
    assert len(detail["chapters"]) >= 2

    tr = client.get(f"/api/v1/lectures/{sample['id']}/transcript", headers=auth_headers).json()
    assert tr["timed"] is True
    assert len(tr["segments"]) > 20

    search = client.post(
        f"/api/v1/lectures/{sample['id']}/transcript/search",
        json={"q": "newton second law force mass acceleration"},
        headers=auth_headers,
    )
    assert search.status_code == 200
    assert search.json()["items"], "expected search hits for a core topic"


def test_bookmarks_roundtrip(client: TestClient, auth_headers: dict) -> None:
    items = client.get("/api/v1/lectures", headers=auth_headers).json()["items"]
    sample = next(l for l in items if l["source"] == "sample")
    created = client.post(
        f"/api/v1/lectures/{sample['id']}/bookmarks",
        json={"ts": 90.0, "label": "F = ma"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    bm_id = created.json()["id"]
    listed = client.get(f"/api/v1/lectures/{sample['id']}/bookmarks", headers=auth_headers).json()
    assert any(b["id"] == bm_id for b in listed["items"])
    assert client.delete(f"/api/v1/lectures/bookmarks/{bm_id}", headers=auth_headers).status_code == 204


def test_transcript_upload(client: TestClient, auth_headers: dict) -> None:
    items = client.get("/api/v1/lectures", headers=auth_headers).json()["items"]
    sample = next(l for l in items if l["source"] == "sample")
    srt = b"1\n00:00:00,000 --> 00:00:02,000\nUploaded cue\n"
    resp = client.post(
        f"/api/v1/lectures/{sample['id']}/transcript",
        files={"file": ("captions.srt", srt, "application/x-subrip")},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["segments"][0]["text"] == "Uploaded cue"
    assert resp.json()["source"] == "upload"
    # restore the sample transcript for other tests
    from app.seed import _SAMPLE
    from app.services.lecture_service import store_segments
    from app.services.transcript import ParsedSegment

    db = SessionLocal()
    try:
        lecture = db.get(__import__("app.models", fromlist=["Lecture"]).Lecture, sample["id"])
        store_segments(db, lecture, [ParsedSegment(s, e, t) for s, e, t in _SAMPLE], source="sample")
    finally:
        db.close()


# ---------------------------------------------------------------- tutor / notes / quiz
def _sample_id(client: TestClient, auth_headers: dict) -> int:
    items = client.get("/api/v1/lectures", headers=auth_headers).json()["items"]
    return next(l for l in items if l["source"] == "sample")["id"]


def test_tutor_answer_is_grounded(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    resp = client.post(
        f"/api/v1/lectures/{lid}/tutor/ask",
        json={"question": "What does Newton's second law say?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] in ("demo", "ollama", "gemini")
    assert data["references"], "answer must cite transcript timestamps"
    assert any(term in data["answer"].lower() for term in ("f = m", "force", "mass", "acceleration", "f equals m", "m times a"))


def test_tutor_unanswerable_question(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    resp = client.post(
        f"/api/v1/lectures/{lid}/tutor/ask",
        json={"question": "What is the capital of France?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "couldn't find" in resp.json()["answer"].lower() or "doesn't" in resp.json()["answer"].lower()


def test_tutor_requires_transcript(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/lectures/999999/tutor/ask",
        json={"question": "hello"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.fixture()
def trailer_id(client: TestClient, auth_headers: dict) -> int:
    from app.models import Lecture, TranscriptSegment
    with SessionLocal() as db:
        sample = db.get(Lecture, _sample_id(client, auth_headers))
        clip = Lecture(user_id=sample.user_id, video_id="tutor-trailer", url="",
                       title="Countdown to Avengers: Doomsday | Every Moment on Disney+",
                       source="upload", transcript_status="ready")
        db.add(clip)
        db.flush()
        for i, (start, end, text) in enumerate([
            (1.04, 6.08, "We lost friends. We lost family."),
            (6.08, 11.44, "Today we have a chance to take it all back."),
            (19.119, 24.199, "This is the fight of our lives."),
            (33.04, 38.76, "Avengers assemble."),
        ]):
            db.add(TranscriptSegment(lecture_id=clip.id, idx=i, start=start, end=end, text=text))
        db.commit()
        return clip.id


def test_tutor_avengers_overview_uses_the_loaded_captions(client, auth_headers, trailer_id):
    resp = client.post(f"/api/v1/lectures/{trailer_id}/tutor/ask",
                       json={"question": "Explain Avengers in simple terms?"}, headers=auth_headers)
    assert resp.status_code == 200
    result = resp.json()
    assert ("lost friends" in result["answer"] or "friends" in result["answer"].lower())
    assert "Avengers" in result["answer"]
    assert "couldn't find" not in result["answer"]
    assert "upload" not in result["answer"].lower()
    assert result["references"]
    assert result["notice"] if result["mode"] == "demo" else result["notice"] is None


def test_tutor_does_not_link_unrelated_sources_when_not_covered(client, auth_headers, trailer_id):
    result = client.post(f"/api/v1/lectures/{trailer_id}/tutor/ask",
                         json={"question": "What is the capital of France?"}, headers=auth_headers).json()
    assert "couldn't find" in result["answer"]
    assert result["references"] == []
    assert "upload" not in result["answer"].lower()


def test_tutor_rejects_invented_model_timestamps(client, auth_headers, trailer_id, monkeypatch):
    monkeypatch.setattr("app.routers.tutor.ai.complete_text", lambda *a, **k: ("Aliens invented them [99:59].", "gemini"))
    result = client.post(f"/api/v1/lectures/{trailer_id}/tutor/ask",
                         json={"question": "Explain Avengers in simple terms?"}, headers=auth_headers).json()
    assert result["mode"] == "demo"
    assert "Aliens" not in result["answer"]
    assert "99:59" not in result["answer"]
    assert result["references"]


def test_tutor_follow_up_can_use_persisted_user_history(client, auth_headers, monkeypatch):
    lid = _sample_id(client, auth_headers)
    prompts = []
    def generate(prompt, **kwargs):
        prompts.append(prompt)
        return "Newton's second law is F equals m times a [1:20].", "gemini"
    monkeypatch.setattr("app.routers.tutor.ai.complete_text", generate)
    first = client.post(f"/api/v1/lectures/{lid}/tutor/ask",
                        json={"question": "Explain Newton's second law"}, headers=auth_headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/lectures/{lid}/tutor/ask",
                         json={"question": "Explain that more simply"}, headers=auth_headers)
    assert second.status_code == 200
    assert "user: Explain Newton's second law" in prompts[-1]
    assert second.json()["references"]


def test_notes_generate_and_export(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    resp = client.post(
        f"/api/v1/lectures/{lid}/notes/generate",
        json={"kind": "summary"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    note = resp.json()
    assert note["mode"] in ("demo", "ollama", "gemini")
    assert note["content_md"].startswith("#")

    md = client.get(f"/api/v1/notes/{note['id']}/export?format=md", headers=auth_headers)
    assert md.status_code == 200
    assert "Summary" in md.text

    pdf = client.get(f"/api/v1/notes/{note['id']}/export?format=pdf", headers=auth_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_definitions_note(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    resp = client.post(
        f"/api/v1/lectures/{lid}/notes/generate",
        json={"kind": "definitions"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert "inertia" in resp.json()["content_md"].lower() or "force" in resp.json()["content_md"].lower()


def test_quiz_generate_grade_and_mastery(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    gen = client.post(
        f"/api/v1/lectures/{lid}/quiz/generate",
        json={"count": 5, "difficulty": "mixed"},
        headers=auth_headers,
    )
    assert gen.status_code == 201, gen.text
    quiz = gen.json()
    assert len(quiz["questions"]) == 5
    assert all("answer" not in q for q in quiz["questions"]), "answers must be hidden while taking"

    answers = []
    for q in quiz["questions"]:
        if q["type"] == "mcq":
            answers.append({"question_id": q["id"], "answer": q["options"][0]})
        else:
            answers.append({"question_id": q["id"], "answer": "because the lecture said so about the object"})
    attempt = client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts",
        json={"answers": answers},
        headers=auth_headers,
    )
    assert attempt.status_code == 200, attempt.text
    data = attempt.json()
    assert data["count"] == 5
    assert 0.0 <= data["score"] <= 1.0
    assert isinstance(data["gaps"], list)

    history = client.get("/api/v1/quiz-history", headers=auth_headers)
    assert history.status_code == 200
    assert any(h["id"] == data["attempt_id"] for h in history.json()["items"])


# ---------------------------------------------------------------- progress / flashcards
def test_progress_overview(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/progress/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "totals" in data and "recommendations" in data
    assert data["mode"] in ("demo", "ollama", "gemini")


def test_watch_progress_persists_max(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    client.post(f"/api/v1/lectures/{lid}/progress", json={"seconds": 40}, headers=auth_headers)
    client.post(f"/api/v1/lectures/{lid}/progress", json={"seconds": 15}, headers=auth_headers)
    resp = client.get(f"/api/v1/lectures/{lid}/progress", headers=auth_headers)
    assert resp.json()["seconds"] == 40


def test_flashcards_generate_and_review(client: TestClient, auth_headers: dict) -> None:
    lid = _sample_id(client, auth_headers)
    stats_before = client.get("/api/v1/flashcards/stats", headers=auth_headers).json()

    gen = client.post(
        f"/api/v1/lectures/{lid}/flashcards/generate",
        json={"count": 5},
        headers=auth_headers,
    )
    assert gen.status_code == 201, gen.text
    cards = gen.json()["items"]
    assert len(cards) >= 3

    # Counters must reflect the saved deck, not any review queue.
    stats_after_gen = client.get("/api/v1/flashcards/stats", headers=auth_headers).json()
    assert stats_after_gen["total"] >= stats_before["total"] + 3
    assert stats_after_gen["due"] >= stats_after_gen["total"] - stats_before["total"] + stats_before["due"]
    all_cards = client.get("/api/v1/flashcards?due=false", headers=auth_headers).json()["items"]
    due_cards = client.get("/api/v1/flashcards?due=true", headers=auth_headers).json()["items"]
    assert stats_after_gen["total"] == len(all_cards) or len(all_cards) == 100  # list caps at 100
    assert stats_after_gen["due"] == len(due_cards)

    reviewed = client.post(
        f"/api/v1/flashcards/{cards[0]['id']}/review",
        json={"quality": 3},
        headers=auth_headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["interval_days"] > 0

    # A saved review moves the card out of "due" but never removes it from the deck.
    stats_after_review = client.get("/api/v1/flashcards/stats", headers=auth_headers).json()
    assert stats_after_review["total"] == stats_after_gen["total"]
    assert stats_after_review["due"] == stats_after_gen["due"] - 1
    due_ids = {c["id"] for c in client.get("/api/v1/flashcards?due=true", headers=auth_headers).json()["items"]}
    assert cards[0]["id"] not in due_ids


# ---------------------------------------------------------------- video jobs
def test_explainer_job_refuses_demo_output(client,auth_headers):
    import time
    lid=_sample_id(client,auth_headers)
    r=client.post(f'/api/v1/lectures/{lid}/explainer-videos',json={'concept':'Newton law','complexity':'beginner'},headers=auth_headers)
    assert r.status_code==201
    for _ in range(60):
        job=client.get(f"/api/v1/video-jobs/{r.json()['id']}",headers=auth_headers).json()
        if job['status']=='failed':break
        time.sleep(.05)
    assert job['status']=='failed' and not job['video_url']


def test_scene_plan_rejects_bad_types() -> None:
    from app.services.manim_templates import PlanValidationError, validate_scene_plan

    with pytest.raises(PlanValidationError):
        validate_scene_plan({"scenes": [{"type": "import os", "heading": "x", "narration": "y"}]})
    with pytest.raises(PlanValidationError):
        validate_scene_plan({"scenes": []})


# ---------------------------------------------------------------- dashboard / health
def test_dashboard(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["lectures"] >= 1
    assert len(data["activity"]) == 14


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["gemini"] == "unconfigured"


def test_protected_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/lectures").status_code == 401
    assert client.get("/api/v1/dashboard").status_code == 401


def test_public_preview_returns_actual_generated_answer_with_sample_sources(client, monkeypatch):
    from app.routers.ai_preview import _requests
    _requests.clear()
    monkeypatch.setattr("app.routers.ai_preview.ai.complete_text", lambda *a, **k: ("Monomers join into long polymer chains [2:14].", "gemini"))
    response = client.post("/api/v1/ai/preview", json={"question": "What is a polymer?"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "gemini"
    assert data["references"][0]["start"] == 134
    assert "Monomers" in data["answer"]


def test_public_preview_does_not_disguise_failure_as_scripted_ai(client, monkeypatch):
    monkeypatch.setattr("app.routers.ai_preview.ai.complete_text", lambda *a, **k: ("", "demo"))
    response = client.post("/api/v1/ai/preview", json={"question": "What is a polymer?"})
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_public_preview_rejects_invented_sources(client, monkeypatch):
    monkeypatch.setattr("app.routers.ai_preview.ai.complete_text", lambda *a, **k: ("Made-up answer [9:59].", "gemini"))
    response = client.post("/api/v1/ai/preview", json={"question": "What is a polymer?"})
    assert response.status_code == 502


def test_ai_status_does_not_expose_credentials(client):
    data = client.get("/api/v1/ai/status").json()
    assert data["state"] == "unconfigured"
    assert "api_key" not in data


def test_quiz_invalid_ai_shape_is_labelled_as_fallback(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.routers.quiz.ai.complete_json", lambda *a, **k: ({"unexpected": []}, "gemini"))
    lid = _sample_id(client, auth_headers)
    response = client.post(f"/api/v1/lectures/{lid}/quiz/generate",
                           json={"count": 3, "difficulty": "easy"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["mode"] == "demo"
    assert len(response.json()["questions"]) == 3


def test_gateway_rejects_truncated_provider_output(monkeypatch):
    from types import SimpleNamespace
    from app.services.ai import AIError, _generate
    response = SimpleNamespace(text='{"questions": [', candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))
    monkeypatch.setattr("app.services.ai._get_client", lambda: client)
    with pytest.raises(AIError, match="truncated"):
        _generate("Make a quiz", None, None, 0.2)


@pytest.fixture()
def rendered_job(client, auth_headers, tmp_path):
    from app.models import Lecture, VideoJob
    lecture_id = _sample_id(client, auth_headers)
    payload = b"media-response-fixture-for-authenticated-range-tests"
    from app.config import settings
    video = Path(settings.storage_dir)/"range-test"/"explainer.mp4"
    video.parent.mkdir(parents=True,exist_ok=True)
    import shutil,subprocess
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:pytest.skip('FFmpeg is required for the real media transport fixture')
    subprocess.run([ffmpeg,'-y','-loglevel','error','-f','lavfi','-i','color=c=black:s=64x64:d=1','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t','1','-c:v','libx264','-c:a','aac','-shortest',str(video)],check=True,capture_output=True)
    payload=video.read_bytes()
    with SessionLocal() as db:
        lecture = db.get(Lecture, lecture_id)
        job = VideoJob(lecture_id=lecture.id, user_id=lecture.user_id, concept="Media test",
                       status="completed", stage="Completed with narration", progress=100,
                       video_path=str(video))
        db.add(job)
        db.commit()
        return {"id": job.id, "payload": payload}


def test_video_owner_can_fetch_and_seek_media(client, auth_headers, rendered_job):
    path = f"/api/v1/video-jobs/{rendered_job['id']}/download?kind=mp4"
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.content == rendered_job["payload"]
    partial = client.get(path, headers={**auth_headers, "Range": "bytes=0-7"})
    assert partial.status_code == 206
    assert partial.content == rendered_job["payload"][:8]
    assert partial.headers["content-range"] == f"bytes 0-7/{len(rendered_job['payload'])}"


def test_video_remains_private_to_its_owner(client, rendered_job):
    path = f"/api/v1/video-jobs/{rendered_job['id']}/download?kind=mp4"
    assert client.get(path).status_code == 401
    signup = client.post("/api/v1/auth/signup", json={"email": "media-other@example.com", "password": "test-password-123", "name": "Other media user"})
    assert signup.status_code == 201
    headers = {"Authorization": "Bearer " + signup.json()["access_token"]}
    assert client.get(path, headers=headers).status_code == 404


def test_video_is_not_advertised_while_audio_is_still_muxing(client, auth_headers, rendered_job):
    from app.models import VideoJob
    with SessionLocal() as db:
        job = db.get(VideoJob, rendered_job["id"])
        job.status = "muxing"
        db.commit()
    response = client.get(f"/api/v1/video-jobs/{rendered_job['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["video_url"] is None
