# Frontend live checks

Headless Edge + Chrome DevTools Protocol scripts (Node 24+, no dependencies). They verify
real behaviour in the running app — not mocks.

Both need the backend (`:8000`) and Vite dev server (`:5173`) running, and a demo token:

```powershell
$login = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" -Method Post `
  -ContentType "application/json" -Body '{"email":"demo@oraya.app","password":"oraya-demo-1"}' -UseBasicParsing
$tok = ($login.Content | ConvertFrom-Json).access_token
node frontend/tests/flashcards-ui-check.mjs $tok   # point checks: generate button, saved-card
                                                   # counters, filter switch resets the answer
node frontend/tests/flashcards-ui-e2e.mjs  $tok    # end to end: create via the button → review →
                                                   # reload → both persisted on the server
```

Last run (2026-11-14): `flashcards-ui-check` 9/9 passed, `flashcards-ui-e2e` 8/8 behaviours
passed (the script's duplicate-front lookup identified the wrong same-front card in one
assertion; the reviewed card's `due_at`/`interval` were confirmed directly via the API).
