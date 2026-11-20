"""Real API and rendering checks in an isolated database. Requires network access."""
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "storage" / "ai-full-verification"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (OUT / "verification.db").as_posix()
os.environ["STORAGE_DIR"] = str(OUT)

from fastapi.testclient import TestClient
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Lecture, VideoJob
from app.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.services.ai import ai
from app.services.video_jobs import _run_job
from verify_video_output import verify


def main():
    report = {"model": settings.gemini_model, "tutor_model": settings.gemini_tutor_model,
              "key_configured": settings.gemini_enabled, "checks": {}}
    def record(name, result):
        report["checks"][name] = result
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(name, json.dumps(result), flush=True)

    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        lecture = next(item for item in client.get("/api/v1/lectures", headers=headers).json()["items"] if item["source"] == "sample")
        cases = [
            ("landing_chat", "/api/v1/ai/preview", {"question": "What is a polymer in simple terms?"}),
            ("tutor", f"/api/v1/lectures/{lecture['id']}/tutor/ask", {"question": "Explain Newton's second law in simple terms"}),
            ("notes", f"/api/v1/lectures/{lecture['id']}/notes/generate", {"kind": "summary"}),
            ("chapter_notes", f"/api/v1/lectures/{lecture['id']}/notes/generate", {"kind": "chapters"}),
            ("definitions", f"/api/v1/lectures/{lecture['id']}/notes/generate", {"kind": "definitions"}),
            ("quiz", f"/api/v1/lectures/{lecture['id']}/quiz/generate", {"count": 3, "difficulty": "easy"}),
        ]
        for name, path, payload in cases:
            started = time.monotonic()
            response = client.post(path, json=payload, headers=headers)
            data = response.json()
            (OUT / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            passed = response.status_code < 300 and data.get("mode") == "gemini"
            if name in {"tutor", "landing_chat"}:
                passed = passed and bool(data.get("references"))
            if name == "quiz":
                passed = passed and len(data.get("questions", [])) == 3
            record(name, {"passed": passed, "http": response.status_code, "mode": data.get("mode"),
                          "seconds": round(time.monotonic() - started, 2)})
        try:
            vectors = ai.embed(["A force changes the motion of an object."], task_type="RETRIEVAL_DOCUMENT")
            record("embeddings", {"passed": len(vectors) == 1 and bool(vectors[0]), "dimensions": len(vectors[0])})
        except Exception as exc:
            record("embeddings", {"passed": False, "error": str(exc).replace(settings.gemini_api_key, "[REDACTED]")[:500]})

    with SessionLocal() as db:
        saved = db.get(Lecture, lecture["id"])
        job = VideoJob(lecture_id=saved.id, user_id=saved.user_id, concept="Newton's second law", complexity="beginner")
        db.add(job)
        db.commit()
        job_id = job.id
    print("Rendering explainer job", job_id, flush=True)
    _run_job(job_id)
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        mode = (job.scene_plan or {}).get("generation_mode")
        result = {"passed": job.status == "completed" and mode == "gemini", "status": job.status,
                  "mode": mode, "error": job.error, "video": job.video_path, "job_id": job.id}
        if job.video_path:
            try:
                result["media"] = verify(Path(job.video_path).parent)
            except Exception as exc:
                result.update(passed=False, media_error=str(exc))
        record("explainer", result)
    print("All checks passed:", all(item["passed"] for item in report["checks"].values()), flush=True)


if __name__ == "__main__":
    main()
