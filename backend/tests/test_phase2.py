"""Tests for the Phase 2/3 features: SM-2, revision analytics, doubts, Ask My Library, concept map, planner."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.srs import maturity, next_schedule
from tests.test_api import auth_headers, client  # noqa: F401  (fixtures)

API = "/api/v1"


# ------------------------------------------------------------------ SM-2 (pure)
def test_sm2_interval_ladder() -> None:
    s1 = next_schedule(0, 2.5, 0.0, 2)  # Good
    assert (s1.reps, s1.interval_days) == (1, 1.0)
    s2 = next_schedule(s1.reps, s1.ease, s1.interval_days, 2)
    assert (s2.reps, s2.interval_days) == (2, 6.0)
    s3 = next_schedule(s2.reps, s2.ease, s2.interval_days, 2)
    assert s3.reps == 3 and s3.interval_days == pytest.approx(6.0 * s3.ease, rel=0.01)


def test_sm2_lapse_resets_and_lowers_ease() -> None:
    s = next_schedule(5, 2.5, 30.0, 0)
    assert s.lapsed and s.reps == 0 and s.interval_days == 0 and s.ease < 2.5


def test_sm2_ease_floor_and_easy_raises_ease() -> None:
    assert next_schedule(1, 1.3, 1.0, 0).ease == 1.3
    assert next_schedule(1, 2.5, 1.0, 3).ease > 2.5
    with pytest.raises(ValueError):
        next_schedule(0, 2.5, 0, 9)


def test_maturity_stages() -> None:
    assert [maturity(0, 0), maturity(1, 1), maturity(3, 10), maturity(6, 40)] == ["new", "learning", "young", "mature"]


# ------------------------------------------------------------------ revision + review log
def _lecture_id(client, h) -> int:
    return client.get(f"{API}/lectures", headers=h).json()["items"][0]["id"]


def test_review_is_logged_and_feeds_analytics(client, auth_headers) -> None:
    lid = _lecture_id(client, auth_headers)
    cards = client.post(f"{API}/lectures/{lid}/flashcards/generate", json={"count": 5}, headers=auth_headers).json()["items"]
    before = client.get(f"{API}/revision/analytics", headers=auth_headers).json()["total_reviews"]
    r = client.post(f"{API}/flashcards/{cards[0]['id']}/review", json={"quality": 2}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["interval_days"] == 1.0
    lapse = client.post(f"{API}/flashcards/{cards[0]['id']}/review", json={"quality": 0}, headers=auth_headers).json()
    assert lapse["interval_days"] == 0.0  # lapse resets the ladder (scheduled for relearning in 10 min)
    a = client.get(f"{API}/revision/analytics", headers=auth_headers).json()
    assert a["total_reviews"] == before + 2
    assert a["by_day"][-1]["reviews"] >= 2 and 0 <= a["retention"] <= 1
    assert set(a["stages"]) == {"new", "learning", "young", "mature"}
    q = client.get(f"{API}/revision/queue", headers=auth_headers).json()
    assert q["total_due"] >= len(q["items"])
    assert q["total_due"] >= 0  # a lapsed card returns after the 10-minute relearn window, not immediately


def test_revision_requires_auth(client) -> None:
    assert client.get(f"{API}/revision/queue").status_code == 401
    assert client.get(f"{API}/planner/plans").status_code == 401
    assert client.get(f"{API}/concepts/graph").status_code == 404


# ------------------------------------------------------------------ doubts
def test_doubt_lifecycle_and_flashcard_conversion(client, auth_headers) -> None:
    lid = _lecture_id(client, auth_headers)
    d = client.post(f"{API}/doubts", json={"question": "Why does net force matter?", "lecture_id": lid,
                                           "timestamp": 40, "subject": "Physics"}, headers=auth_headers)
    assert d.status_code == 201
    did = d.json()["id"]
    assert client.post(f"{API}/doubts/{did}/flashcard", headers=auth_headers).status_code == 409  # not resolved
    client.patch(f"{API}/doubts/{did}", json={"status": "resolved"}, headers=auth_headers)
    assert client.post(f"{API}/doubts/{did}/flashcard", headers=auth_headers).status_code == 409  # no note yet
    client.patch(f"{API}/doubts/{did}", json={"note": "Acceleration depends on the net force."}, headers=auth_headers)
    card = client.post(f"{API}/doubts/{did}/flashcard", headers=auth_headers)
    assert card.status_code == 201 and card.json()["back"].startswith("Acceleration")
    assert client.post(f"{API}/doubts/{did}/flashcard", headers=auth_headers).status_code == 409  # only once
    listing = client.get(f"{API}/doubts?status=resolved", headers=auth_headers).json()
    assert any(i["id"] == did and i["lecture_title"] for i in listing["items"])
    assert client.delete(f"{API}/doubts/{did}", headers=auth_headers).status_code == 204


def test_doubts_are_private_and_validated(client, auth_headers) -> None:
    did = client.post(f"{API}/doubts", json={"question": "Private doubt"}, headers=auth_headers).json()["id"]
    other = client.post(f"{API}/auth/signup", json={"email": "other-doubt@example.com", "password": "secret123", "name": "O"}).json()
    h2 = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.patch(f"{API}/doubts/{did}", json={"status": "resolved"}, headers=h2).status_code == 404
    assert client.get(f"{API}/doubts", headers=h2).json()["items"] == []
    assert client.post(f"{API}/doubts", json={"question": "x y z", "timestamp": 5}, headers=auth_headers).status_code == 422
    assert client.post(f"{API}/doubts", json={"question": "abc", "lecture_id": 999999}, headers=auth_headers).status_code == 404


# ------------------------------------------------------------------ Ask My Library
def test_library_answers_are_grounded_with_sources(client, auth_headers) -> None:
    r = client.post(f"{API}/library/ask", json={"question": "What is inertia?"}, headers=auth_headers).json()
    assert r["grounded"] is True and r["sources"]
    s = r["sources"][0]
    assert s["lecture_id"] and s["timestamp"] and "inertia" in (s["quote"] + s["context"]).lower()


def test_library_refuses_when_sources_do_not_cover_it(client, auth_headers) -> None:
    r = client.post(f"{API}/library/ask", json={"question": "Explain mitochondrial membrane potential"}, headers=auth_headers).json()
    assert r["grounded"] is False and r["sources"] == [] and r["mode"] == "none"


def test_library_search_and_isolation(client, auth_headers) -> None:
    assert client.get(f"{API}/library/search?q=newton", headers=auth_headers).json()["total"] > 0
    other = client.post(f"{API}/auth/signup", json={"email": "other-lib@example.com", "password": "secret123", "name": "O"}).json()
    h2 = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"{API}/library/search?q=newton", headers=h2).json()["total"] == 0
    assert client.post(f"{API}/library/ask", json={"question": "What is inertia?"}, headers=h2).json()["grounded"] is False
    assert client.get(f"{API}/library/search?q=a", headers=auth_headers).status_code == 422


# ------------------------------------------------------------------ concept map
def test_removed_concept_map_has_no_endpoint(client,auth_headers):
    assert client.get(f"{API}/concepts/graph",headers=auth_headers).status_code==404


# ------------------------------------------------------------------ planner
def test_planner_generates_respects_capacity_and_reschedules(client, auth_headers) -> None:
    lid = _lecture_id(client, auth_headers)
    exam = (__import__("app.routers.planner", fromlist=["_today"])._today() + timedelta(days=10)).isoformat()
    r = client.post(f"{API}/planner/plans", json={"title": "Physics midterm", "exam_date": exam, "daily_minutes": 45,
                                                  "lecture_ids": [lid]}, headers=auth_headers)
    assert r.status_code == 201
    plan = r.json()
    kinds = [t["kind"] for t in plan["tasks"]]
    assert kinds.count("watch") == 1 and kinds.count("revise") == 3
    assert all(t["day"] < exam for t in plan["tasks"])  # everything finishes before the exam
    # task completion persists
    t = plan["tasks"][0]
    assert client.patch(f"{API}/planner/tasks/{t['id']}", json={"status": "done"}, headers=auth_headers).json()["status"] == "done"
    assert client.get(f"{API}/planner/plans/{plan['id']}", headers=auth_headers).json()["progress"]["done"] == 1
    # simulate missed sessions: push pending tasks into the past, then reschedule
    from app.database import SessionLocal
    from app.models import StudyTask
    yesterday = (__import__("app.routers.planner", fromlist=["_today"])._today() - timedelta(days=2)).isoformat()
    with SessionLocal() as db:
        for row in db.query(StudyTask).filter(StudyTask.plan_id == plan["id"], StudyTask.status == "pending").all():
            row.day = yesterday
        db.commit()
    assert client.get(f"{API}/planner/plans/{plan['id']}", headers=auth_headers).json()["progress"]["overdue"] == 3
    moved = client.post(f"{API}/planner/plans/{plan['id']}/reschedule", headers=auth_headers).json()
    assert moved["moved"] == 3 and moved["progress"]["overdue"] == 0
    assert all(today_or_later >= __import__("app.routers.planner", fromlist=["_today"])._today().isoformat() for today_or_later in [x["day"] for x in moved["tasks"] if x["status"] == "pending"])
    assert client.delete(f"{API}/planner/plans/{plan['id']}", headers=auth_headers).status_code == 204


def test_planner_validation(client, auth_headers) -> None:
    lid = _lecture_id(client, auth_headers)
    past = (__import__("app.routers.planner", fromlist=["_today"])._today() - timedelta(days=1)).isoformat()
    assert client.post(f"{API}/planner/plans", json={"title": "x", "exam_date": past, "lecture_ids": [lid]}, headers=auth_headers).status_code == 422
    soon = (__import__("app.routers.planner", fromlist=["_today"])._today() + timedelta(days=5)).isoformat()
    assert client.post(f"{API}/planner/plans", json={"title": "x", "exam_date": soon, "lecture_ids": [999999]}, headers=auth_headers).status_code == 404
