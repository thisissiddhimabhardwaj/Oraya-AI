# Gemini post-HTTP response parsing investigation

15 November 2026. Only `backend/app/services/ai.py`, the new `backend/tests/test_gemini_response_parsing.py`, and this report were changed by this task. No frontend, production database, API routes, response schemas, model configuration or video pipeline changes were made. No GitHub operations occurred. No .env edits were performed; that file's hash changed during execution outside these edits and was left intact.

## What the supplied logs prove

The provider returned HTTP 200, followed by an application-side exception whose classification had no numeric HTTP status. That is not proof of billing, model unavailability, a tool call or a safety block. The three supplied lines contain neither the SDK response metadata nor a traceback, so the exact historical Python exception cannot honestly be reconstructed from them.

The old post-response path accessed `response.candidates`, rejected MAX_TOKENS with a generic AIError, then accessed the SDK convenience `response.text` property and rejected empty text with another generic AIError. Those output errors defaulted to provider_unavailable/503. The failover layer classified them as PROVIDER_ERROR because they were not HTTP errors; it logged decision=next_model but in fact raised on that branch. Other Python parsing exceptions could produce the same logs. A malformed response could also raise inside the SDK before generate_content returned.

## Actual baseline SDK inspection

Installed SDK: google-genai 3.3.0. Its response.text property invokes a helper that reads only the first candidate, serializes non-text part fields to warn about them, and omits thought parts. This convenience serialization is unnecessary for ORAYA's plain-text interface.

A real isolated authenticated Tutor baseline request succeeded before the code changes: endpoint HTTP 200 in 5.454 seconds, Gemini mode and nonempty generated answer. The actual returned structure was:

- GenerateContentResponse, one Candidate, finish reason STOP.
- One Part containing 409 characters of non-thought text.
- No function call, no blocked safety rating or prompt block.
- Zero automatic-function-calling history entries.

No text, prompt, transcript, key, headers or response body was printed. This baseline did not reproduce the historical lecture-45 failure, and it does not establish the contents of that failed request's response.

## Changes

- Extract text directly from candidate.content.parts rather than response.text. SDK typed objects and equivalent snake/camel-case mappings are supported. Concatenate text parts, omit thought text, and select a complete safe text candidate even when an earlier candidate is unusable.
- Distinguish EMPTY_RESPONSE, OUTPUT_TRUNCATED, SAFETY_BLOCK, UNEXPECTED_FUNCTION_CALL, INCOMPLETE_RESPONSE, SDK_RESPONSE_PARSE_ERROR, SDK_GENERATION_ERROR and INVALID_STRUCTURED_OUTPUT. Do not label successful-transport output failures as quota or model-access failures.
- Return complete nonempty candidate text immediately. A non-text/function-call part alongside valid complete text is not executed and does not hide the usable text. Function-call-only output is not accepted as an answer. Safety-blocked output is rejected transparently rather than routing around the block.
- Disable automatic function calling explicitly using the installed SDK's supported AutomaticFunctionCallingConfig(disable=True). This gateway configures no tools, so it has no legitimate tool execution/continuation to perform. The prior AFC max_remote_calls=10 informational message was not proof that tools were actually invoked; the real baseline had no AFC history.
- SDK/part parsing errors preserve the original cause. Output failures may advance to the next eligible configured model without same-model SDK/application retry loops or false quota cooldowns. Safety blocks stop with a typed output error. Genuine HTTP authentication/quota/server errors retain their existing handling.
- Log only safe response metadata: candidate/part counts, text lengths, thought/function counts, known finish/block enums, token counts and AFC history count. Do not log tool names, arguments, thought text, response bodies or HTTP headers.
- Log sanitized original exception class and basename:line:function, including failures inside SDK accessors. An AttributeError raised inside an existing descriptor is preserved rather than mistaken for a missing optional field. Correct decision logs distinguish reject from next_model.
- Gemini 3.6 remains primary, followed by 3.7, 3.8 and Ollama. Authentication, context/history construction and Tutor citation validation are unchanged.

## Post-fix live verification: blocked, not passed

Two post-fix isolated authenticated Tutor attempts used the existing configured credentials and a temporary SQLite database/storage. Both were rejected by Google **before a successful generation response**:

- Gemini 3.6 generateContent: HTTP 401, UNAUTHENTICATED.
- Sanitized actual exception: google.genai.errors.ClientError, `errors.py:216:raise_error`.
- ORAYA Tutor: HTTP 502, `provider_auth`.
- Only Gemini 3.6 was attempted; credentials were not retried indefinitely or hidden behind a mock response.

The second attempt followed observation that .env changed during the run and used a fresh process reading the current file. The current failure is authentication, not post-HTTP-200 parsing. No further attempts were made. **A successful post-fix live Tutor response containing actual Gemini text cannot be claimed until configured credentials authorize generation again.** No key was requested or exposed.

## Tests

Focused provider/response/video run: **84 passed**. The new module contributes 21 cases covering real SDK text parts, thought filtering, convenience-property failure avoidance, mapping structures, alternate candidates, function-call-only and mixed parts, empty/missing/whitespace/thought-only candidates, safety blocks, truncation, original parse causes/locations, disabled AFC, primary success without fallback, SDK generation parse errors, invalid HTTP-200 error classification and authenticated Tutor delivery of candidate text.

These regression tests explicitly mock provider responses. The authenticated regression uses a separate temporary owned lecture and verifies the exact returned answer and Gemini mode. It cleans up its own records, avoiding cross-test lecture ordering effects. No mocked test is counted as successful live Gemini verification.

Full backend suite: **176 passed, 10 failed, 0 skipped**. The same ten pre-existing demo-success/provider-status expectation tests fail:

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

Commands from backend:

```sh
python3 -m pytest tests/test_gemini_response_parsing.py tests/test_primary_36.py tests/test_ai_reliability.py tests/test_ai_quota.py tests/test_exact_provider_logs.py tests/test_video_reliability.py -q
python3 -m pytest tests -q
```

SHA-256 checks confirmed all frontend files and the existing backend/oraya.db were unchanged. The .env change was observed, not overwritten or restored. Restart the backend to load the response-handling changes. The remaining live acceptance blocker is Google's authentication rejection; the historical exception still requires a recurrence with the newly added sanitized diagnostics to identify conclusively.
