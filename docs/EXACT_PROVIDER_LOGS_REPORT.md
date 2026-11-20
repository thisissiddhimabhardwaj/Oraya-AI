# Exact Gemini/Ollama log fixes — 15 November 2026

## Findings and fixes

Gemini 2.5 Flash was tested with actual minimal generation requests using the existing local key. Both `/v1` and `/v1beta` returned HTTP 404, `NOT_FOUND`. Google's sanitized message states that this model is **“no longer available to new users”** and recommends Gemini 3.8. The restriction is provider-side model access under this API configuration, not billing, an invalid key, or a retryable connection failure. The model remains configurable and first in the requested priority. A confirmed 404 now categorically remains `MODEL_UNAVAILABLE`, with only that model cooling down for five minutes. The same key successfully generated with Gemini 3.6.

Gemini 3.8 returned a real HTTP 429 with:

- `GenerateRequestsPerDayPerProjectPerModel-FreeTier`
- model `gemini-3.8-flash`, location `global`
- quota value `20`
- retry delay `7766` seconds in the direct diagnostic request (later requests showed a naturally decreasing remaining delay)

This is now `DAILY_QUOTA_EXHAUSTED`, scope `model`. The supplied retry period is used directly; midnight reset is only a fallback when no delay is supplied. A deterministic regression reproduces the user's original 8570-second payload and verifies the exact expiry. Other models remain eligible.

The billing misclassification came from matching **any occurrence of “billing”** in an error message. Google's ordinary quota guidance mentions plan/billing details, so this created a false project-wide restriction. The fix requires explicit restriction language or a recognized billing ErrorInfo reason. Structured per-model quota evidence takes precedence over generic guidance. A 404 cannot become billing regardless of its message.

A second diagnostic problem was that project cooldown state was returned while considering another model and logged as though that model had produced the billing error. Cooldowns now retain `source_model`, with separate provider/scope/model/quota identities including metric IDs and dimensions. Cooldown logs distinguish `blocked_model`, `source_model` and scope. Genuine shared project restrictions still stop all cloud attempts; an ordinary per-model quota does not.

The exact configurable priority remains:

`gemini-2.5-flash` → `gemini-3.8-flash` → `gemini-3.7-flash` → `gemini-3.6-flash` → Ollama `qwen3:4b`.

Bounded 503 retries retain actual RetryInfo/Retry-After handling. SDK attempts remain one. No infinite fallback loop or generated mock answer was added.

## Actual provider checks

| Request | Actual result |
| --- | --- |
| Gemini 2.5, v1beta | 404, model unavailable, 0.532 seconds |
| Gemini 2.5, v1 | 404, model unavailable, 0.304 seconds |
| Gemini 3.8, v1beta | 429, model-specific daily quota of 20, retry delay 7766 seconds |
| Gemini 3.7, v1beta | 429; provider metadata named **Gemini 3.8**, retry delay 7765 seconds |
| Gemini 3.6, v1beta | 200, actual nonempty generated text, 9.948 seconds |
| Ollama Qwen3 4B | Reachable, exact model installed, actual nonempty generated text with expected marker, 4.253 seconds |

The 3.7 response's dimensions naming 3.8 are preserved as returned. This does not establish a shared project quota, and the successful 3.6 request confirms that cloud generation was still possible. No model-list result was treated as proof of generation access.

Ollama success is only returned after content and any required JSON schema have been validated. HTTP 200 with empty text, truncated/incomplete output, or an unexpected response shape is rejected with a specific output error. Local failures now have safe failure logs, and known output/timeout error codes are preserved rather than always being wrapped as a generic unavailable code. No prompts, transcripts, tokens, headers or keys were printed.

## Actual authenticated Tutor requests

Both requests used a temporary SQLite database and temporary storage, with the existing Tutor API route and authentication.

1. Normal cloud priority: Gemini 2.5 returned 404; 3.8/3.7 returned daily quotas; **Gemini 3.6 handled the Tutor request**, returning HTTP 200 in **12.479 seconds**. The response validated as `TutorAnswer`, contained generated text and four source references.
2. Explicit local-only test configuration in a separate temporary process: **Ollama qwen3:4b handled the Tutor request**, returning HTTP 200 in **55.206 seconds**, with a valid `TutorAnswer`, nonempty generated text and one reference. Instrumentation confirmed that the actual provider input retained conversation history and lecture/transcript context. This test did not edit `.env` and did not pretend that all live Gemini models had failed.

Deterministic tests separately verify that Gemini failures followed by Ollama success return the local answer, preserving identical prompt/system/history/lecture/document inputs. Real Ollama generation was not mocked in the live checks.

## Video polling

The previous ExplainerPanel ran `/video-jobs` every **2500 milliseconds unconditionally**, even with an empty job list or only terminal jobs.

It now fetches once when the lecture mounts/changes, then polls only while that lecture has active jobs. Completed, failed and render-skipped jobs stop polling. Creation/retry immediately updates the job state and fetches status, starting active polling again. The active cadence remains 2500 milliseconds after each response; recursive scheduling prevents overlapping requests when an API response takes longer. Cleanup cancels future polls.

Only the polling/state integration in ExplainerPanel changed. No JSX layout, CSS, class names, typography, navigation or animations were redesigned. Polling behavior was verified through four deterministic timer tests and a successful production build; no manual browser request-count measurement is claimed.

## AI Explainer and MP4 verification

The existing video service, database models, routes and response schemas were unchanged. A real local-only central-service call generated a two-scene plan with Qwen3 4B, validated it with the existing VideoScript schema, and rendered it through the existing local pipeline.

Actual output: `backend/storage/exact-verification-20261115/explainer.mp4`.

FFprobe validation: **13.465215 seconds**, H.264 video, AAC audio and mov_text subtitles. Local narration status: **available=true**. Ollama generated the scene plan; the existing renderer produced pixels, narration and MP4 assembly. Existing authenticated download/range-playback/isolation tests passed. Cloud video production itself was not re-tested or changed.

## Files modified or added

- `backend/app/services/ai_quota.py` — precise classification, explicit daily retry window, independent quota identities and origin attribution.
- `backend/app/services/ai.py` — correct cooldown log attribution and truthful validation/failure reporting for Ollama responses.
- `backend/tests/test_exact_provider_logs.py` (new) — nine targeted regressions for the supplied logs, independent cooldowns, explicit billing, context fallback and invalid HTTP-200 local outputs.
- `frontend/src/components/ExplainerPanel.jsx` — active-job-only polling and immediate creation/retry state integration; no visual changes.
- `frontend/src/lib/videoJobPolling.js` (new) — small cancellable polling scheduler and active-job predicate.
- `frontend/tests/video-job-polling.test.mjs` (new) — four deterministic polling tests.
- `docs/EXACT_PROVIDER_LOGS_REPORT.md` (new) — this report.
- `docs/EXACT_PROVIDER_LOGS_CHANGED_FILES.txt` (new) — exact source/build/generated-asset inventory from the pre-task snapshot.

The production build also regenerated `frontend/dist`; its full inventory is in the changed-files list. Smoke-test media/validation/subtitle files are listed separately there. No unrelated source files were modified.

SHA-256 comparison confirms the existing `backend/.env`, `backend/oraya.db`, and `backend/app/services/video_jobs.py` are unchanged. No GitHub access, commits or pushes occurred. Existing credentials were used only in Google's authentication mechanism.

## Tests executed

- Initial focused backend run: **54 passed**, no failures/skips; an additional explicit-billing regression was then included in the final full run.
- Final full backend suite: **147 passed, 10 failed, 0 skipped**. All nine new exact-log regressions pass. The ten failures are the same pre-existing demo-success/provider-status expectation failures documented before this task; no production mock responses were introduced to satisfy them.
- Polling unit tests: **4 passed, 0 failed/skipped**.
- ESLint for the modified frontend source files: **passed**.
- Frontend production build: **passed** (existing large-chunk advisory only).
- Live checks: Gemini 2.5 access **failed 404 as reported**; 3.8/3.7 generation **failed 429 as reported**; 3.6 generation/Tutor **passed**; Ollama generation/local Tutor **passed**; actual local narrated MP4 **passed**. No live checks were skipped.

Remaining full-suite failures:

`test_tutor_answer_is_grounded`, `test_tutor_avengers_overview_uses_the_loaded_captions`, `test_notes_generate_and_export`, `test_definitions_note`, `test_quiz_generate_grade_and_mastery`, `test_progress_overview`, `test_health`, `test_ai_status_does_not_expose_credentials`, `test_library_answers_are_grounded_with_sources`, `test_no_silent_ai_fallback`.

## Run and remaining limits

Restart the backend to load the changes and discard any false project-wide cooldown retained by an older running process. Do not run another backend on the occupied port; stop the existing one with Ctrl+C first.

```sh
cd '/Users/rishika/Downloads/oraya 3/ORAYA/backend'
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tests:

```sh
cd '/Users/rishika/Downloads/oraya 3/ORAYA/backend'
python -m pytest tests/test_exact_provider_logs.py tests/test_ai_quota.py tests/test_ai_reliability.py tests/test_video_reliability.py -q
python -m pytest tests -q
cd '/Users/rishika/Downloads/oraya 3/ORAYA/frontend'
node --test tests/video-job-polling.test.mjs
npm run build
```

A Vite development server will reload the polling source changes; a production frontend needs the rebuilt dist assets loaded. Cooldowns remain process-local, so separate backend workers do not share them. Code cannot restore provider access to Gemini 2.5 or replenish the account's exhausted daily quota. Gemini 3.6 and local Qwen were actually working during this verification; that does not guarantee future provider capacity.
