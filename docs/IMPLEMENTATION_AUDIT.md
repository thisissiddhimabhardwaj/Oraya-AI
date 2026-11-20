# Premium transformation audit — 15 November 2026

Scope: the existing independent `oraya-rebuild` copy. Original workspace source and GitHub remain untouched. Source and private runtime backups were made separately before editing, under `/private/tmp/ORAYA-before-premium-pass-20261115.zip` and a private runtime backup directory. Neither backup is included in the delivery archive.

## Findings before this pass

| Workflow | Verified source finding | Action |
|---|---|---|
| Tutor / Notes → shared AI facade | No configured Gemini key. Both correctly failed closed, but generic errors obscured the cause; model configuration required verification. | Add explicit unconfigured/auth/model/quota/timeout errors and authenticated model-access check. Keep real generation, source context and citation validation. Default model uses documented Gemini structured-output support. Live generation still requires a key. |
| Revision entry → analytics → Flashcards | The old Revision page showed statistics and linked elsewhere. It had no persisted recall-session workflow of its own. | Replace the page with answer/reveal/rate sessions, persisted cursor/answers, real SM-2 scheduling, upcoming/weak/mastered views, calendar and review history. |
| Explainer → background job → optional Manim | Missing Manim/FFmpeg. Old service allowed render_skipped and silent completion and replaced rejected plans with demo templates. | Replace with strict script validation, Pillow illustrations, configured speech, measured audio, SRT, FFmpeg scenes/transitions, MP4 mux and FFprobe validation. Failure remains failure. |
| Spatial entry → hardcoded arrays | Six predefined arrays were the primary product. No generation, saved environment, source-aware object tutoring or persisted challenge results. | Add strict typed scene schema, generated jobs/ownership APIs, validated reusable renderer, browser, source selector, object tutor, guided steps, challenges and saved progress. Move arrays behind optional demos. |
| Concept Map | Standalone page/API/navigation existed. | Remove product page, route, navigation and API. Topic mastery stays because revision/quiz analytics use it. |
| Secondary feature navigation | Rooms/comparison/doubts distracted from core flow. | Hide standalone frontend routes/navigation; preserve historical database records and backend services. No replacement standalone features added. |
| Logout | Sidebar logout existed, but top account control was only a profile link. | Add a clear profile/account menu with logout. Keep server JWT revocation and client credential clearing. |
| Layout | Multiple tool panels remain mounted for state preservation. Legacy height limits and CSS could produce nested scroll regions. | Enforce hidden panels, remove workspace height caps/nested scrolling, bound grid children/canvas, namespace new landing styles, test six requested viewports. |

## Current architecture

React/Vite/React Router/Tailwind, FastAPI, SQLAlchemy and SQLite retained. New additive tables: `spatial_environments`, `spatial_responses`, `revision_sessions`, `revision_responses`; migration version 5 records this extension. No PostgreSQL, Redis or arbitrary model-authored executable code is introduced. AI-generated scene data is validated with Pydantic and rendered through a fixed Three.js geometry vocabulary.

Background states persist in SQLite. Queued jobs resume on startup; interrupted in-progress jobs become retryable failures. A single local video worker bounds CPU use; two scene workers bound generation concurrency. This is a single-process local deployment, not a distributed worker service.

## Provider and renderer checks

No Gemini key was configured at initial audit. FFmpeg/FFprobe and Manim were absent. FFmpeg/FFprobe were installed for real rendering verification. macOS speech works when the process can access the OS speech service; sandboxed speech returned empty audio, which was rejected. A subsequent authorized local renderer check produced a real narrated MP4 with audio, video and subtitle streams. This used an authored test script and is not evidence of live Gemini generation.

Gemini model/schema reference: https://ai.google.dev/gemini-api/docs/structured-output and https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash. Model access must still be checked against the configured account and quota.

## Security and correctness gates

Ownership is checked for scene/job/session retrieval and mutation; challenge scoring and revision scheduling happen on the server. Scene limits constrain objects, coordinates, dimensions, materials, references and animation definitions. No eval, arbitrary scripts, URLs, shaders or generated Python execution are accepted. Media downloads are constrained to private storage. Scene answers remain hidden until response submission. Invalid model output and missing media tools produce persisted failure states.

See TEST_REPORT.md for actual results, not inferred functionality. FEATURE_COMPLETION.md and KNOWN_LIMITATIONS.md distinguish completed code, verified persistence and external-service blockers.
