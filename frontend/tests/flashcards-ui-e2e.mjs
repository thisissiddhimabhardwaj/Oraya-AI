// End-to-end UI test: create flashcards via the button, review one, reload, verify persistence.
import { spawn } from "node:child_process";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const APP = "http://127.0.0.1:5173";
const PORT = 9334;
const TOKEN = process.argv[2];
const results = [];
const consoleErrors = [];
const ok = (name, pass, detail = "") => {
  results.push({ name, pass });
  console.log(`${pass ? "PASS" : "FAIL"} | ${name}${detail ? " | " + detail : ""}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stats = async () => (await fetch(`${APP}/api/v1/flashcards/stats`, { headers: { Authorization: `Bearer ${TOKEN}` } })).json();

const proc = spawn(EDGE, [
  "--headless=new",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=C:\\Users\\saksh\\AppData\\Local\\Temp\\opencode\\edge-profile-e2e-${Date.now()}`,
  "--no-first-run", "--no-default-browser-check", "--disable-gpu", "about:blank",
], { stdio: "ignore" });

let ws; let msgId = 0;
const pending = new Map();
const send = (method, params = {}, sessionId) => {
  const id = ++msgId;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  ws.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => { if (pending.delete(id)) reject(new Error(`timeout: ${method}`)); }, 30000);
  });
};
const evaluate = async (expression, sessionId) => {
  const res = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, sessionId);
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.text || "evaluate failed");
  return res.result?.value;
};

try {
  let wsUrl = null;
  for (let i = 0; i < 40 && !wsUrl; i++) {
    try { wsUrl = (await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json()).webSocketDebuggerUrl; }
    catch { await sleep(500); }
  }
  if (!wsUrl) throw new Error("Edge CDP endpoint never came up");
  ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description ?? "").join(" "));
    } else if (msg.method === "Runtime.exceptionThrown") {
      consoleErrors.push("exception: " + (msg.params.exceptionDetails.text || ""));
    }
  };

  const { targetId } = await send("Target.createTarget", { url: `${APP}/login` });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  await send("Page.enable", {}, sessionId);
  await send("Runtime.enable", {}, sessionId);
  await sleep(1500);
  await evaluate(`localStorage.setItem("oraya_token", ${JSON.stringify(TOKEN)})`, sessionId);
  await send("Page.navigate", { url: `${APP}/flashcards` }, sessionId);
  for (let i = 0; i < 40; i++) {
    if (await evaluate(`!!document.querySelector('form[aria-label="Create flashcards"]')`, sessionId)) break;
    await sleep(400);
  }

  // ---- 1. CREATE through the real button
  const before = await stats();
  const create = await evaluate(`(async () => {
    const form = document.querySelector('form[aria-label="Create flashcards"]');
    if (!form) return { step: 'no-form' };
    const select = form.querySelector('#flashcard-lecture');
    const lecture = select?.value;
    const btn = [...form.querySelectorAll('button')].find((b) => b.textContent.includes('Generate flashcards'));
    if (!btn) return { step: 'no-button' };
    btn.click();
    const t0 = Date.now();
    while (Date.now() - t0 < 25000) {
      const notice = document.querySelector('[role="status"]');
      if (notice && /ready in your deck/.test(notice.textContent)) {
        return { step: 'done', lecture, notice: notice.textContent.slice(0, 140) };
      }
      const err = form.querySelector('[role="alert"]');
      if (err) return { step: 'error', message: err.textContent.slice(0, 200) };
      await new Promise((r) => setTimeout(r, 400));
    }
    return { step: 'timeout' };
  })()`, sessionId, 30000);
  ok("creation via Generate button works", create?.step === "done", JSON.stringify(create));

  const afterCreate = await stats();
  ok("created cards saved on server", afterCreate.total >= before.total && afterCreate.total > 0,
     `total ${before.total} -> ${afterCreate.total} (due ${before.due} -> ${afterCreate.due})`);

  const uiAfterCreate = await evaluate(`document.querySelector('[aria-label="Filter flashcards"]')?.textContent`, sessionId);
  ok("counters match server stats after creation",
     uiAfterCreate?.includes(`All (${afterCreate.total})`) && uiAfterCreate?.includes(`Due (${afterCreate.due})`),
     `UI: ${uiAfterCreate} | server: total=${afterCreate.total} due=${afterCreate.due}`);

  // ---- 2. REVIEW one card through the UI
  const review = await evaluate(`(async () => {
    const show = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Show answer'));
    if (!show) return { step: 'no-show-button' };
    show.click();
    await new Promise((r) => setTimeout(r, 350));
    const front = document.querySelector('section[aria-label="Flashcard review"] h2')?.textContent;
    const good = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Good') && x.className.includes('rounded-2xl'));
    if (!good) return { step: 'no-quality-button' };
    good.click();
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) {
      const notice = document.querySelector('[role="status"]');
      if (notice && /Review saved/.test(notice.textContent)) return { step: 'done', front, notice: notice.textContent.slice(0, 140) };
      await new Promise((r) => setTimeout(r, 300));
    }
    return { step: 'timeout' };
  })()`, sessionId, 20000);
  ok("review saved through the UI", review?.step === "done", JSON.stringify(review));

  const afterReview = await stats();
  ok("review persisted (due -1, total unchanged)", afterReview.total === afterCreate.total && afterReview.due === afterCreate.due - 1,
     `total ${afterCreate.total} -> ${afterReview.total}, due ${afterCreate.due} -> ${afterReview.due}`);

  // ---- 3. RELOAD: everything must still be true
  await send("Page.navigate", { url: `${APP}/flashcards` }, sessionId);
  for (let i = 0; i < 40; i++) {
    if (await evaluate(`!!document.querySelector('h1')?.textContent?.includes('Flashcards')`, sessionId)) break;
    await sleep(400);
  }
  await sleep(1200);
  const uiAfterReload = await evaluate(`document.querySelector('[aria-label="Filter flashcards"]')?.textContent`, sessionId);
  ok("counters survive reload", uiAfterReload?.includes(`All (${afterReview.total})`) && uiAfterReload?.includes(`Due (${afterReview.due})`),
     `UI: ${uiAfterReload} | server: total=${afterReview.total} due=${afterReview.due}`);

  const reviewedCardDue = await (async () => {
    const idMatch = review?.front;
    if (!idMatch) return null;
    const list = await (await fetch(`${APP}/api/v1/flashcards?due=false`, { headers: { Authorization: `Bearer ${TOKEN}` } })).json();
    const card = list.items.find((c) => c.front === idMatch);
    return card ? { front: card.front, due_at: card.due_at } : null;
  })();
  ok("reviewed card rescheduled to the future",
     reviewedCardDue && new Date(reviewedCardDue.due_at).getTime() > Date.now(),
     JSON.stringify(reviewedCardDue));

  ok("no console errors during the flow", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" || "));
} catch (err) {
  ok("script completed", false, String(err));
} finally {
  try { ws?.close(); } catch { /* ignore */ }
  proc.kill();
  const failed = results.filter((r) => !r.pass).length;
  console.log(`\n== ${results.length - failed}/${results.length} checks passed ==`);
}
