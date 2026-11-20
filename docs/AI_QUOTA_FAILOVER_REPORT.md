# ORAYA quota and provider failover report

Verified locally on 15 November 2026. Backend-only changes; no repository remote access, commits, pushes, publication or frontend changes.

## A. Files changed

| File | Change |
| --- | --- |
| `backend/app/config.py` | Defaults to Gemini 2.5 Flash, adds the fourth Gemini slot and configurable admission/retry waits; adds Qwen structured-thinking control. |
| `backend/.env.example` | Documents exact model order and new settings with no credentials. |
| `backend/app/services/ai_quota.py` (new) | Parses Google error payloads, RetryInfo/Retry-After, quota metrics/dimensions/values and scopes; implements synchronized process-local cooldowns. |
| `backend/app/services/ai.py` | Central quota-aware failover; avoids 429 retry loops and probe calls; preserves exception causes; adds safe diagnostics, cloud admission control, embedding cooldown checks, truthful Ollama errors and Qwen JSON thinking control. |
| `backend/app/routers/ai_preview.py` | Reports effective generation models and makes the existing authenticated provider check respect cooldowns/admission limits. Existing routes and required response fields remain. |
| `backend/tests/test_ai_reliability.py` | Updates the previous priority tests for four Gemini candidates and removes the obsolete assumption that unknown 429s should retry the same model; isolates quota state. |
| `backend/tests/test_ai_quota.py` (new) | 25 deterministic quota/failover/concurrency/security/context tests. |
| `backend/verify_ai_providers.py` (new) | Explicit live verification command, prints only status/latency/sanitized metadata and nonempty-text results. Live failures return a nonzero exit code; skips are labeled. |
| `docs/AI_QUOTA_FAILOVER_REPORT.md` (new) | This report. |

Generated verification artifacts: `backend/storage/quota-verification-20261115/explainer.mp4`, `validation.json`, `subtitles.srt`, `narration-status.json`. These are standalone test assets, not production VideoJob records.

## Audit and root cause

The previous application retry helper classified every HTTP 429 as transient and retried each model with roughly one/two-second backoff. It did not inspect Google QuotaFailure, ErrorInfo or RetryInfo details, retain model/project cooldowns, distinguish billing restrictions, or coordinate concurrent requests. An additional minimal generation probe preceded the real request, consuming quota twice. The SDK was already set to one attempt; the observed repeated retries originated in the application layer. That one-attempt SDK setting remains.

The existing tutor/preview/library prompts already contain history and retrieved source context. The Ollama adapter receives those same constructed prompt/system strings. JSON output validation remains centralized using JSON Schema; video scripts also retain Pydantic validation. The existing video provider is separate from text generation and was not changed.

## Provider selection and error handling

Effective default order confirmed at runtime:

1. `gemini-2.5-flash`
2. `gemini-3.8-flash`
3. `gemini-3.7-flash`
4. `gemini-3.6-flash`
5. Ollama `qwen3:4b`

Environment controls are `GEMINI_PRIMARY_MODEL`, `GEMINI_FALLBACK_MODEL_1`, `_2`, `_3`, `OLLAMA_BASE_URL` and `OLLAMA_MODEL`. Existing variables are retained. Explicit new settings can override this default order. Duplicate/empty model entries are removed to prevent accidental loops. A successful actual generation establishes access; no model-list result is treated as proof of generation/quota availability, and no extra generation probe precedes normal requests.

- Model-specific RPM/TPM: immediate next model, no same-model retry, default 60-second cooldown extended by provider delays.
- Model-specific RPD: immediate next model, cooldown until the next midnight Pacific reset, or a longer explicit provider delay.
- Shared project quota, including shared TPM: skip remaining Gemini requests and use Ollama. Merely seeing a project identifier does not prove the limit is shared; model dimensions/per-model quota IDs take precedence over that assumption.
- Billing/spend restriction: project cooldown (at least five minutes) and local fallback, including billing-related 403s. Ordinary authentication/authorization/malformed-request errors still stop immediately.
- Temporary capacity: bounded same-model retries, using the greater of jittered backoff, Retry-After and RetryInfo delay. Delays above the configurable ten-second in-request sleep budget trigger cooldown and next-model/local failover without calling that model early.
- Unknown 429: `UNKNOWN_QUOTA_LIMIT`; no daily-quota claim and no same-model retry. Safe metadata is retained, with the original cloud exception accessible on an ultimate AIError.
- Temporary 5xx/connection/timeout failures: bounded retries (default three, maximum four); final failures cause short cooldowns. Model-specific 404: no retry, five-minute model cooldown.

Cooldowns expire automatically and live only in this API process. A bounded admission lock prevents concurrent requests from all probing an exhausted cloud quota; callers that cannot enter within ten seconds use local fallback. This deliberately limits cloud concurrency in the current local app. Multiple API worker processes have independent cooldowns; no distributed coordination was introduced.

Google payloads are inspected in memory. Logs/diagnostics retain allowlisted status, categories, metric IDs, quota IDs, numeric quota values, model/location dimensions, delays, decisions and latency. Arbitrary error messages/details, consumer/project IDs, prompts, headers and keys are not logged. The original exception is retained as a cause rather than stringified into the public response. Existing API response schemas are unchanged.

Embedding calls honor shared cooldowns and continue to use the existing lexical retrieval fallback when cloud embeddings are unavailable; they are not incorrectly sent to the text model chain.

## B. Gemini verification

**Live Gemini 2.5 Flash: SKIPPED, not passed.** No `GEMINI_API_KEY` is configured in the process environment, and `backend/.env` was absent both at the start and end of this task. No key was requested, printed or written. No `.env` file was created or overwritten.

Consequently no Gemini HTTP status, generation latency, actual Google quota category/message or quota dimensions can honestly be reported. None of the four Gemini IDs was live-tested. Gemini 2.5 primary success and all quota decisions were tested with explicitly mocked provider responses only. This implementation does not establish that the account's Gemini quota problem is resolved. The live verification command is ready to use when credentials are supplied through the existing environment.

## C. Ollama verification

Ollama was reachable at `http://127.0.0.1:11434`; `qwen3:4b` was installed. A real /api/chat generation returned actual nonempty text with the requested test marker: **PASS**, latency **13.479 seconds**. No different model was substituted. Service reachability and exact local model presence are checked before generation. Missing service/model, HTTP errors, timeout, truncated/empty output and invalid structured results fail truthfully.

The first real schema-constrained scene-generation attempt timed out after the existing 180-second budget. For the Qwen3 family only, JSON requests now explicitly send Ollama's supported `think=false` by default, configurable with `OLLAMA_STRUCTURED_THINKING`; free-text behavior is unchanged. With that adjustment the full live scene-generation/rendering check completed successfully in **26.978 seconds**. No extra provider-specific generation parameter is sent to Gemini or to other Ollama model families.

## D. Real ORAYA request and Explainer

Actual request: POST `/api/v1/ai/preview`, using an isolated temporary database/storage configuration and the application router, with no mock generation responses.

- HTTP **200**, provider **Ollama**, model **qwen3:4b**, latency **46.633 seconds**.
- Instrumentation confirmed the actual provider prompt contained the supplied conversation history and the existing sample lecture context. No user content was printed.
- The returned answer was nonempty, had one source timestamp reference and validated against the existing `TutorAnswer` schema.
- Because Gemini credentials were absent, this was real local-provider selection, not a live reproduction of Google's 429. Shared-quota-to-local transitions are independently covered by deterministic tests.

An additional live call through the central service used Qwen3 4B to generate a two-scene `VideoScript`, validated it, then passed it to the unchanged local educational renderer. FFprobe validated an actual **12.297234-second MP4**, H.264 video, AAC narration and embedded mov_text subtitles. `narration-status.json` reports `available=true`. This verifies that Ollama generated the script/scene plan and the existing renderer generated the video pixels/audio assembly. The cloud video adapter was preserved but was not live-tested/configured here.

Existing media integration tests passed, including real FFmpeg fixture creation, authenticated full download, HTTP 206 range playback, cross-user rejection and incomplete-job playback protection. Persistent production jobs were not created by the standalone live smoke check.

## E. Tests executed

Pre-change baseline: `python3 -m pytest tests -q` → **113 passed, 10 failed**.

After implementation: `python3 -m pytest tests -q` → **138 passed, 10 failed** (148 total; no pytest skips). The same ten test names failed before and after this task. The old suite explicitly expects demo-success responses/status behavior rather than the previous implementation's already-enabled real Ollama fallback. Those expectations were not disguised with production mock responses.

The 25 new tests cover exact priority, model-specific RPM/TPM/RPD/unknown 429, shared project limits, billing 429/403, RetryInfo/Retry-After numeric and HTTP date forms, long delays, cooldown expiry, concurrent admission (20 callers caused one shared-quota cloud attempt), ErrorInfo and response.json parsing, safe metadata/logs, preserved cloud causes, identical history/lecture/document/schema input across providers, embedding/admin-check cooldowns and Qwen-specific JSON controls. The final focused run of quota, provider and video tests passed all **46 tests**.

Remaining baseline failures:

- `test_tutor_answer_is_grounded`
- `test_tutor_avengers_overview_uses_the_loaded_captions`
- `test_notes_generate_and_export`
- `test_definitions_note`
- `test_quiz_generate_grade_and_mastery`
- `test_progress_overview`
- `test_health`
- `test_ai_status_does_not_expose_credentials`
- `test_library_answers_are_grounded_with_sources`
- `test_no_silent_ai_fallback`

Separately executed live checks: Gemini SKIPPED for missing credentials; Ollama generation PASS; ORAYA preview PASS; initial structured scene attempt TIMEOUT; corrected structured scene generation plus narrated MP4 production PASS. No skipped or mocked test is counted as a successful live provider test.

Commands from the local backend directory:

```sh
cd '/Users/rishika/Downloads/oraya 3/ORAYA/backend'
python3 -m pytest tests/test_ai_quota.py tests/test_ai_reliability.py tests/test_video_reliability.py -q
python3 -m pytest tests -q
python3 verify_ai_providers.py
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
ffprobe -v error -show_streams -show_format -of json storage/quota-verification-20261115/explainer.mp4
```

The live verification command makes only a harmless Gemini 2.5 test request when a key is available and a real local Ollama test; it does not modify configuration or the database. A Gemini skip is explicitly printed. It emits no generated text, keys or headers.

## F. Frontend/database/environment protection

**Frontend files modified: NO.** All 61 frontend files outside node_modules matched the pre-task SHA-256 snapshot, including no added or removed files. `backend/oraya.db` also matched its pre-task hash. The existing video service was byte-for-byte unchanged. Tests and live app checks used temporary databases. No `.env` file existed or was changed.

This local copy has no `.git` directory, so a repository-local git diff was unavailable. A pre/post file hash comparison and direct code review were used instead; no parent/original repository was accessed.

## G. Remaining issues

Live Gemini access and Google's actual quota reason remain unverified without configured credentials. The full suite retains the ten pre-existing failures above. Cooldown coordination is process-local. Cloud video generation was not live-tested. Long local model inference can still exceed the finite request timeout; no false success is returned. Qwen JSON thinking remains configurable in case a deployment wants a longer inference tradeoff.

References used for provider semantics: [Google Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) (including Pacific RPD reset), [Google API error guidance](https://ai.google.dev/gemini-api/docs/api-errors), and [Ollama thinking controls](https://github.com/ollama/ollama/blob/main/docs/capabilities/thinking.mdx). Local implementation/test results above come from the actual commands, not these documentation sources.
