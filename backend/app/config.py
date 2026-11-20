from __future__ import annotations

import os
import secrets
from pydantic import Field, model_validator
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ORAYA"
    allow_demo_ai: bool = False
    seed_demo: bool = False
    study_timezone: str = "Asia/Kolkata"
    database_url: str = "sqlite:///./oraya.db"
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_expires_days: int = 30
    jwt_algorithm: str = "HS256"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_primary_model: str = "gemini-3.8-flash"
    gemini_fallback_model_1: str = "gemini-3.7-flash"
    gemini_fallback_model_2: str = "gemini-3.6-flash"
    gemini_fallback_model_3: str = ""
    gemini_thinking_budget: int = 0
    ai_cloud_queue_timeout_seconds: float = 15.0
    ai_max_retry_wait_seconds: float = 8.0
    ai_timeout_ms: int = 25000
    ai_retry_attempts: int = 2
    ai_model_retry_budget_seconds: float = 20.0
    enable_local_fallback: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ollama_structured_thinking: bool = False
    video_generation_provider: str = "auto"
    cloud_video_model: str = ""
    enable_local_video_rendering: bool = True
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    gemini_tutor_model: str = "gemini-3.8-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    storage_dir: str = "./storage"
    ffmpeg_bin_path: str = ""
    ffprobe_bin_path: str = ""
    tts_provider: str = "macos"
    tts_voice: str = "Samantha"

    @model_validator(mode="after")
    def migrate_legacy_gemini_priority(self):
        # Preserve existing .env bytes/credentials while migrating legacy chains.
        # Required priority: gemini-3.8-flash -> gemini-3.7-flash -> gemini-3.6-flash -> Ollama qwen3:4b
        chain=(self.gemini_primary_model,self.gemini_fallback_model_1,
               self.gemini_fallback_model_2,self.gemini_fallback_model_3)
        if chain in (
            ("gemini-2.5-flash","gemini-3.8-flash","gemini-3.7-flash","gemini-3.6-flash"),
            ("gemini-3.6-flash","gemini-3.7-flash","gemini-3.8-flash",""),
        ):
            self.gemini_primary_model="gemini-3.8-flash"
            self.gemini_fallback_model_1="gemini-3.7-flash"
            self.gemini_fallback_model_2="gemini-3.6-flash"
            self.gemini_fallback_model_3=""
        if self.gemini_model in ("gemini-2.5-flash", "gemini-3.6-flash"):
            self.gemini_model=self.gemini_primary_model
        if self.gemini_tutor_model in ("gemini-2.5-flash", "gemini-3.6-flash"):
            self.gemini_tutor_model=self.gemini_primary_model
        return self

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

os.makedirs(settings.storage_dir, exist_ok=True)

# Make the configured ffmpeg/ffprobe discoverable by shutil.which(), pydub and
# subprocess calls regardless of how the process was launched (the inherited PATH
# may predate the installer, and .env may name either the binary or its folder).
def _dir_for(value: str) -> str | None:
    """Resolve a configured path to the directory that must be on PATH.

    Accepts the executable itself (…/ffmpeg.exe) or the directory containing it
    (…/ffmpeg). Returns None for values that resolve to nothing on disk.
    """
    if not value:
        return None
    path = Path(value)
    if path.is_dir():
        return str(path)
    if path.is_file():
        return str(path.parent)
    if path.suffix == "" and path.with_suffix(".exe").is_file():
        return str(path.parent)
    return None


for _bin in (settings.ffmpeg_bin_path.strip(), settings.ffprobe_bin_path.strip()):
    _dir = _dir_for(_bin)
    if _dir and _dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _dir + os.pathsep + os.environ.get("PATH", "")
