"""Opt-in real-network/render smoke check. Run with the rendering environment active."""
from pathlib import Path
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "storage" / "phase05"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (OUT / "verification.db").as_posix()
os.environ["STORAGE_DIR"] = str(OUT)

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Lecture, VideoJob
from app.seed import seed_demo_data
from app.services.ai import ai, _generate
from app.services.video_jobs import _run_job
from app.services.manim_templates import SCENE_TYPES, render_source


def main():
    report = {"key_configured": settings.gemini_enabled, "model": settings.gemini_model}
    if "--pipeline-only" not in os.sys.argv:
        try:
            report["live_response"] = _generate("Reply exactly: ORAYA connection verified.", None, None, 0)
            report["live_gemini"] = "passed"
        except Exception as exc:
            report["live_gemini"] = "failed"
            report["live_error"] = str(exc).replace(settings.gemini_api_key, "[REDACTED]") if settings.gemini_api_key else str(exc)
        print("Live Gemini:", report["live_gemini"], flush=True)
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        # All seven approved templates, including the no-LaTeX formula path.
        plan = {"concept": "Template verification", "scenes": [
            {"type": kind, "heading": kind.replace("_", " ").title(),
             "narration": "A verified template displays this explanation.",
             "bullets": ["First idea", "Second idea"], "formula": "a+b=c", "duration": 3}
            for kind in sorted(SCENE_TYPES)]}
        source = OUT / "templates.py"
        source.write_text(render_source(plan), encoding="utf-8")
        proc = subprocess.run([os.sys.executable, "-m", "manim", "-ql", "--disable_caching", str(source), "OrayaExplainer"],
                              cwd=OUT, capture_output=True, text=True, timeout=900)
        (OUT / "templates-render.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        report["all_templates_render"] = proc.returncode == 0
        print("All templates rendered:", report["all_templates_render"], flush=True)
    else:
        report["prior_live_evidence"] = json.loads((OUT / "live-text-success.json").read_text())
        print("Running pipeline only; prior live text request passed.", flush=True)
    init_db()
    with SessionLocal() as db:
        seed_demo_data(db)
        lecture = db.query(Lecture).first()
        job = VideoJob(lecture_id=lecture.id, user_id=lecture.user_id, concept="Newton's second law", complexity="beginner")
        db.add(job)
        db.commit()
        job_id = job.id
    original = ai.complete_json
    modes = []
    def observed(*args, **kwargs):
        result = original(*args, **kwargs)
        modes.append(result[1])
        return result
    ai.complete_json = observed
    try:
        _run_job(job_id)
    finally:
        ai.complete_json = original
    with SessionLocal() as db:
        job = db.get(VideoJob, job_id)
        report.update(job_id=job_id, script_modes=modes, status=job.status,
                      stage=job.stage, error=job.error, video_path=job.video_path)
        if job.video_path:
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", job.video_path],
                                   capture_output=True, text=True, check=True)
            report["probe"] = json.loads(probe.stdout)
            decode = subprocess.run(["ffmpeg", "-v", "error", "-i", job.video_path, "-f", "null", "-"],
                                    capture_output=True, text=True)
            report["decode_passed"] = decode.returncode == 0 and not decode.stderr.strip()
    (OUT / f"report-{job_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "probe"}, indent=2))


if __name__ == "__main__":
    main()
