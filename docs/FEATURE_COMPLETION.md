# Feature completion — 15 November 2026

“Implemented” describes connected code. Live provider verification is a separate gate.

| Feature | Implementation / backend | Persistence and verification | External requirements |
|---|---|---|---|
| Premium landing | Implemented; 12 editorial compositions, functional anchors/auth CTAs, interactive labeled previews | Six requested viewport captures; no section overlaps or horizontal overflow | None |
| Auth / account / logout | Connected registration/login/profile; JWT verification/revocation; account-menu logout; cross-tab and expiry clearing | API ownership/logout tests; browser registration/login and protected-route redirect after logout | Stable private JWT_SECRET |
| Upload / transcript / library | Connected TXT/PDF/caption ingestion, retrieval, search, manual notes/cards | Real biology TXT uploaded through UI; database/ownership tests | YouTube requires network and available captions; scanned PDFs need OCR outside this implementation |
| Tutor / Notes | Real Gemini integration, source references and explicit configuration/provider errors | Source/ownership/error contracts tested; live output NOT verified because key is absent | Gemini key, model access, quota/network |
| Quiz / Exam | Connected generation/scoring/history; manual question workflows retained | API tests pass; generated content NOT live verified | Gemini for generated questions |
| Smart Revision | Implemented answer → reveal → recall rating → SM-2; persisted/resumable sessions; due/overdue/upcoming/weak/mastered/calendar/history; exam-aware prioritization | Full real DB integration test and browser session; refresh retained answer; rating updated next date; date persisted after subsequent login | None for manual cards; Gemini for generated material |
| Explainer | Connected persisted background jobs; strict script → programmatic visuals → TTS → SRT → FFmpeg → validated MP4; authenticated playback/download/retry | Real browser source-excerpt retry completed; playback advanced; downloaded 54.232222s MP4 had video/audio/subtitle streams; 1,057,678 bytes. Live Gemini-authored script NOT verified | FFmpeg/FFprobe; macOS speech or documented gTTS; Gemini for AI explanation |
| Spatial Studio | Connected dynamic topic/source generation APIs, saved environments, strict schema, controlled Three.js renderer, inspector/isolation/guided steps/object tutor/challenges/history | DB/ownership/schema/idempotency tests pass using injected provider contracts. Actual UI persisted honest missing-key failure. Optional demo renderer selection/isolation/resizing tested. Live generated scenes/tutor NOT verified | Gemini; WebGL for viewport |
| Dashboard / planner / memory | Connected to real stored records; no invented statistics | Existing API suite retained/passing | AI-generated plan recommendations need Gemini |
| Concept Map | Removed page/navigation/routes/API and obsolete view styles | Endpoint absence tested | None |
| Rooms / comparison / standalone doubts | Frontend routes/navigation postponed; historical backend records preserved | No new replacement feature | Out of current core journey |

Optional scene demonstrations and marketing previews are explicitly labeled. They are not represented as generated student environments or real performance data. Self-rated revision mastery is not an objective exam score.
