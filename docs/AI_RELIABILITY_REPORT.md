# AI reliability implementation and verification — 15 November 2026

Status: implemented backend changes with verified local media rendering; full cloud/offline AI integration remains blocked and the complete regression suite is not green. No frontend files changed. No commits, pushes, PRs, or publishing performed. The user's .env was not edited.

## Audit and causes

The original gateway selected one model, used SDK retries only, limited tutor/preview calls to 30–35 seconds, cached client initialization failures indefinitely, and had no application failover or Ollama adapter. Structured outputs were parsed as JSON objects without full schema validation. Gemini thinking parameters were selected from a model-name prefix rather than verified capability. Video scripts explicitly rejected non-Gemini providers; rendering used static PNG illustrations with camera zoom. No request logs were supplied, so historical 503/capacity failures cannot be independently attributed to a particular server incident. No configured Gemini key was found by the live settings check; live Gemini generation could not be tested.

## Files changed

- backend/app/config.py
- backend/app/services/ai.py
- backend/app/services/video_jobs.py
- backend/app/services/spatial.py
- backend/app/routers/ai_preview.py
- backend/app/routers/library.py
- backend/app/routers/spatial.py
- backend/app/routers/tutor.py
- backend/app/routers/videos.py
- backend/.env.example
- backend/requirements.txt
- backend/requirements-lock.txt
- backend/tests/test_ai_reliability.py (new)
- backend/tests/test_video_reliability.py (new)
- docs/AI_RELIABILITY_REPORT.md (new)

Generated smoke assets are under backend/storage/reliability-smoke and backend/storage/reliability-narrated. Intermediate frame directories were cleaned after successful rendering.

## Reasoning providers

The shared AI facade now orders gemini-3.8-flash → gemini-3.7-flash → gemini-3.6-flash → qwen3:4b. No alternative model IDs were silently selected. Legacy Gemini environment variables remain accepted, but generation model arguments cannot bypass the ordered chain. Embeddings retain the separate existing Gemini embedding model and lexical fallback.

Each Gemini model is gated by API listing and minimal generation, with successful verification cached for five minutes. Access to all three models remains UNVERIFIED because GEMINI_API_KEY is absent. The authenticated /api/v1/ai/check endpoint performs those checks when credentials are supplied. Model-specific 404 advances without retry; 429, temporary 5xx, transport failures and timeouts have bounded application retries with exponential backoff and jitter. SDK attempts are set to one. Retry-After values over 60 seconds advance failover instead of blocking indefinitely. Credentials and malformed requests fail immediately. No demo-success fallback is returned by the central gateway.

Requests preserve the callers' complete constructed prompt/system instructions, including existing retrieved lecture/document passages and history. Ollama uses its own /api/chat payload and JSON schema format. Both outputs undergo JSON Schema validation. Existing retrieval size limits remain; this is not an unlimited-context implementation. Provider and model success, retry status, and duration are logged without prompt/key content. Per-request last-result status uses ContextVar.

Tutor, library Q&A, notes, quizzes, revision/doubt features and existing spatial generation use the existing central facade; provider gates/citation checks now accept Ollama. Existing routes and response shapes are preserved. No live end-to-end AI feature is claimed tested.

## Ollama

Ollama was already installed and its local service was reachable with sandbox escalation. qwen3:4b was not installed. Its requested download reached approximately 2.3 GB of 2.5 GB, then failed with 'no space left on device'. No existing models or user files were deleted. A partial download may remain in ~/.ollama. Other installed models were deliberately not substituted. Real qwen3:4b inference and complete offline script-to-video generation remain blocked until disk space is available and the pull completes.

## Video

Existing SQLite VideoJob records, authenticated ownership checks, private downloads, worker queue and restart recovery remain in use. Active matching jobs are reused; cross-process simultaneous-creation deduplication is not guaranteed. Worker claims remain atomic. Script plans are Pydantic validated. The renderer executes only fixed application drawing/FFmpeg commands, never generated Python/shell. It animates diagram stage reveal, flow markers and linked concept elements at 12 source frames per second and encodes H.264 at 24 fps. This is programmatic educational animation, not photorealistic generative video.

Local macOS speech is supported; speech failures produce timed subtitles and a silent track with narration availability explicitly recorded in narration-status.json. GET /api/v1/video-jobs/{id}/download?kind=audio-status exposes that artifact under the existing ownership checks. SRT and embedded mov_text subtitles use measured scene timing. Existing FFmpeg/FFprobe variable names remain supported along with the added aliases.

The separate optional cloud adapter calls the configured CLOUD_VIDEO_MODEL through generate_videos, polls with a deadline, downloads scene clips and encodes the assembled video. Unconfigured/failed cloud production falls back to local rendering. Cloud generation is NOT configured or live-tested. Its adapter has deterministic mocked coverage only. Cloud clip narration/subtitle consistency is not yet equivalent to the local timeline; provider-produced audio is retained rather than replaced with the full local narration pipeline.

Actual locally rendered artifact: backend/storage/reliability-narrated/explainer.mp4. FFprobe validated H.264 1280×720 yuv420p, video duration 7.708333 seconds, AAC audio duration 7.728549 seconds, and mov_text subtitles. narration-status.json reports available=true. Validation rejects missing files, missing video, unsupported codec, invalid duration and incomplete video timeline; expected narration requires an audio stream. A separate sandbox test exercised unavailable narration. These used controlled test scripts, NOT scripts generated by an installed Qwen3 4B model. Browser playback and authenticated playback/download of this smoke file were not manually exercised.

## Tests

Final command: python3 -m pytest tests -q (from backend).
Result: 113 passed, 10 failed. All 21 newly added deterministic provider/video tests pass. Coverage includes exact priority, bounded retries, 503, 429, timeout, permanent auth errors, 404, local unavailable/missing model/invalid output, prompt and schema preservation, controlled scene schemas, codec/narration validation, subtitle timestamps, missing renderer, and configured cloud adapter behavior.

Remaining failures:
- test_tutor_answer_is_grounded
- test_tutor_avengers_overview_uses_the_loaded_captions
- test_notes_generate_and_export
- test_definitions_note
- test_quiz_generate_grade_and_mastery
- test_progress_overview
- test_health
- test_ai_status_does_not_expose_credentials
- test_library_answers_are_grounded_with_sources
- test_no_silent_ai_fallback

These include old explicit demo-success expectations and status expectations that do not account for enabled local fallback. They were not rewritten to conceal failures. Additional exhaustive persistent-job, concurrent deduplication and authenticated playback tests remain needed. No claim is made that all requested acceptance cases passed.

Test-isolation incident: during intermediate suite runs, the new test module imported app settings before the existing test_api module assigned temporary database environment variables. These runs may have operated on backend/oraya.db and written test/seed records. The import order was corrected before the final run. No automatic data deletion/restoration was attempted because existing records cannot safely be distinguished without a baseline database backup.

Frontend verification: all 61 files outside node_modules matched the pre-task SHA-256 snapshot. No layouts, styles, navigation or frontend integration code changed.

## Run commands

From the project root:

```sh
cd '/Users/rishika/Downloads/oraya 3/ORAYA/backend'
python3 -m pip install -r requirements.txt
ollama serve
```

In another terminal, after freeing sufficient disk space:

```sh
ollama pull qwen3:4b
cd '/Users/rishika/Downloads/oraya 3/ORAYA/backend'
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Set the additions documented in .env.example in your existing environment as needed. Preserve your existing .env values; GEMINI_API_KEY is required only for Gemini/cloud access. Configure CLOUD_VIDEO_MODEL only with a video model actually accessible to that account. FFmpeg/FFprobe must be installed; local narration uses the existing macOS settings. One API process is recommended with the current in-process worker/recovery design.

```sh
cd '/Users/rishika/Downloads/oraya 3/ORAYA/backend'
python3 -m pytest tests/test_ai_reliability.py tests/test_video_reliability.py -q
python3 -m pytest tests -q
ffprobe -v error -show_streams -show_format -of json storage/reliability-narrated/explainer.mp4
```

Use the unchanged authenticated POST /api/v1/lectures/{id}/explainer-videos endpoint, poll GET /api/v1/video-jobs/{id}, then download GET /api/v1/video-jobs/{id}/download?kind=mp4 when completed. Local end-to-end inference requires finishing the model installation. Full acceptance remains incomplete for the limitations above.
