# Run ORAYA on macOS

Python 3.14 and Node 22+ were used for verification. Work in the independent source; no Git operation is required.

## Install

```sh
brew install python node ffmpeg
cd "/absolute/path/to/ORAYA"
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
python3 scripts/configure_local.py
cp frontend/.env.example frontend/.env
cd frontend
npm ci
```

The configuration script creates backend/.env with a private stable random JWT secret; existing configuration is left unchanged. Edit backend/.env privately. Never send API keys in chat or put them in frontend variables.

## Exact environment variables

```dotenv
DATABASE_URL=sqlite:///./oraya.db
JWT_SECRET=change-me-to-a-long-random-string
JWT_EXPIRES_DAYS=30
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TUTOR_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
STORAGE_DIR=./storage
ALLOW_DEMO_AI=false
SEED_DEMO=false
STUDY_TIMEZONE=Asia/Kolkata
TTS_PROVIDER=macos
TTS_VOICE=Samantha
FFMPEG_BIN_PATH=
FFPROBE_BIN_PATH=
```

The generated JWT secret replaces the placeholder. Gemini needs an API key, model permission, quota and network. Restart after changing backend settings. Blank binary paths use PATH; Apple Silicon Homebrew binaries normally live at /opt/homebrew/bin/ffmpeg and /opt/homebrew/bin/ffprobe (Intel uses /usr/local/bin).

macOS speech is local and requires OS speech access. Check with `say -v Samantha "ORAYA speech check"`. Optional `TTS_PROVIDER=gtts` requires network and transmits narration to that service. No silent fallback is used. Manim is not required.

Frontend .env:

```dotenv
VITE_API_URL=/api/v1
```

## Backend — terminal 1

```sh
cd "/absolute/path/to/ORAYA/backend"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Startup applies additive SQLite migrations through version 5 and recovers jobs. Back up an existing database/storage before upgrading. Use a single backend process; the local queue is not distributed. Keep storage private. Changing JWT_SECRET invalidates existing sessions.

## Frontend — terminal 2

```sh
cd "/absolute/path/to/ORAYA/frontend"
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://localhost:5173 and register. No demo data is seeded. Vite proxies /api to port 8000. For another backend set VITE_API_PROXY=http://127.0.0.1:PORT when launching Vite. API docs: http://127.0.0.1:8000/docs. Stop servers with Ctrl-C.

Manual notes/cards/revision and explicitly selected narrated source excerpts work without Gemini. Generated AI content requires the real provider and otherwise reports an actionable failure. Authenticated POST /api/v1/ai/check checks account/model access.

## Verification

```sh
cd "/absolute/path/to/ORAYA/backend"
.venv/bin/python -m pytest -q tests
.venv/bin/python ../scripts/verify_renderer.py
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

Renderer verification uses an authored test script and writes to the system temp directory; it is not live Gemini acceptance. It requires FFmpeg/FFprobe and OS speech access. Static type checks cover the dynamic scene renderer/schema; legacy JSX has lint/build checks. Follow KNOWN_LIMITATIONS.md for live-provider acceptance.

## Clean source archive

From ORAYA root, use new output and empty verification paths:

```sh
python3 scripts/package_source.py --output /private/tmp/ORAYA-source.zip --verify-dir /private/tmp/ORAYA-source-check
```

The packer excludes secrets, databases, user media, dependencies, caches and Git metadata; it verifies ZIP CRC, extraction safety and SHA-256 source checksums. No original repository is modified.
