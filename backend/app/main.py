from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import SessionLocal, init_db
from .routers import auth, dashboard, learning, lectures, notes, quiz, tutor, videos
from .routers import studio, materials, spatial, revision_sessions
from .routers import ai_preview, doubts, library, planner, revision
from .seed import seed_demo_data
from .services.video_jobs import renderer_status

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _startup() -> None:
    from .migrations import migrate
    migrate()
    from .services.spatial import recover_scenes
    from .services.video_jobs import recover_jobs
    recover_scenes()
    recover_jobs()
    db = SessionLocal()
    try:
        if settings.seed_demo:
            seed_demo_data(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _startup()
    yield


app = FastAPI(
    title="ORAYA API",
    version="1.0.0",
    description="AI-powered personalized interactive learning platform.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    spatial.router,
    revision_sessions.router,
    studio.router,
    materials.router,
    ai_preview.router,
    auth.router,
    lectures.router,
    tutor.router,
    notes.router,
    quiz.router,
    learning.router,
    learning.overview_router,
    learning.cards_router,
    videos.router,
    dashboard.router,
    revision.router,
    doubts.router,
    library.router,
    planner.router,
):
    app.include_router(router, prefix="/api/v1")


@app.exception_handler(__import__("app.services.ai", fromlist=["AIError"]).AIError)
async def ai_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=getattr(exc,"status",503), content={"detail": str(exc),"code":getattr(exc,"code","provider_unavailable")})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
    logging.getLogger("oraya").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server"})


@app.get("/api/v1/health")
@app.get("/health")  # alias for uptime probes (Render, load balancers, dev tooling)
def health() -> dict:
    from .services.ai import ai

    try:
        init_db()
        db_ok = True
    except Exception:  # pragma: no cover
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "gemini": {"available": "live", "unavailable": "unavailable", "not_checked": "configured", "unconfigured": "unconfigured"}[ai.status["state"]],
        "ai_status": ai.status,
        "model": settings.gemini_model if ai.mode == "gemini" else None,
        "renderer": renderer_status(),
    }


@app.get("/api/v1/meta")
def meta() -> dict:
    """Frontend boot config (no secrets)."""
    from .services.ai import ai

    return {
        "app": "ORAYA",
        "ai_mode": ai.mode,
        "renderer": renderer_status(),
        "demo_account": {"email": "demo@oraya.app", "password": "oraya-demo-1"} if settings.seed_demo else None,
    }
