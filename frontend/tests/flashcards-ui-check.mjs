// Live UI verification for ORAYA /flashcards (headless Edge + CDP, no deps).
import { spawn } from "node:child_process";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const APP = "http://127.0.0.1:5173";
const PORT = 9333;
const TOKEN = process.argv[2];
const results = [];
const consoleErrors = [];
const ok = (name, pass, detail = "") => {
  results.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"} | ${name}${detail ? " | " + detail : ""}`);
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const proc = spawn(EDGE, [
  "--headless=new",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=C:\\Users\\saksh\\AppData\\Local\\Temp\\opencode\\edge-profile-${Date.now()}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-gpu",
  "about:blank",
], { stdio: "ignore" });

let ws;
let msgId = 0;
const pending = new Map();
const events = [];

function send(method, params = {}, sessionId) {
  const id = ++msgId;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  ws.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => { if (pending.delete(id)) reject(new Error(`timeout: ${method}`)); }, 20000);
  });
}

async function evaluate(expression, sessionId) {
  const res = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, sessionId);
  if (res.exceptionDetails) throw new Error(res.exceptionDetails.text || "evaluate failed");
  return res.result?.value;
}

async function waitFor(expression, sessionId, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try { if (await evaluate(expression, sessionId)) return true; } catch { /* keep polling */ }
    await sleep(300);
  }
  return false;
}

try {
  // 1. connect to the browser endpoint
  let wsUrl = null;
  for (let i = 0; i < 40 && !wsUrl; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      wsUrl = (await res.json()).webSocketDebuggerUrl;
    } catch { await sleep(500); }
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
    } else if (msg.method) {
      events.push(msg);
      if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
        consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description ?? "").join(" "));
      }
      if (msg.method === "Runtime.exceptionThrown") {
        consoleErrors.push("exception: " + (msg.params.exceptionDetails.text || ""));
      }
    }
  };

  // 2. open the app, inject the session token, go to /flashcards
  const { targetId } = await send("Target.createTarget", { url: `${APP}/login` });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  await send("Page.enable", {}, sessionId);
  await send("Runtime.enable", {}, sessionId);
  await sleep(1500);
  await evaluate(`localStorage.setItem("oraya_token", ${JSON.stringify(TOKEN)})`, sessionId);
  await send("Page.navigate", { url: `${APP}/flashcards` }, sessionId);

  const loaded = await waitFor(`document.querySelector('h1')?.textContent?.includes('Flashcards')`, sessionId, 20000);
  ok("flashcards page renders", loaded);
  await sleep(1200); // let decks/stats settle

  // 3. issue #1: a generate button must exist
  const genBtn = await evaluate(`(() => {
    const btns = [...document.querySelectorAll('button')];
    const b = btns.find((x) => x.textContent.trim().includes('Generate flashcards'));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return { visible: r.width > 0 && r.height > 0, disabled: b.disabled,
             lectureOptions: document.querySelectorAll('#flashcard-lecture option').length };
  })()`, sessionId);
  ok("generate button exists and is visible", !!genBtn && genBtn.visible && !genBtn.disabled,
     genBtn ? `lecture options: ${genBtn.lectureOptions}` : "button not found");

  // 4. issue #3: counters show saved-card totals (compare with the API stats)
  const stats = await (await fetch(`${APP}/api/v1/flashcards/stats`, { headers: { Authorization: `Bearer ${TOKEN}` } })).json();
  const counters = await evaluate(`(() => {
    const group = document.querySelector('[aria-label="Filter flashcards"]');
    return group ? group.textContent : null;
  })()`, sessionId);
  const dueOk = counters?.includes(`Due (${stats.due})`);
  const allOk = counters?.includes(`All (${stats.total})`);
  ok("filter counters show saved-card stats", dueOk && allOk,
     `UI: ${counters} | API stats: total=${stats.total} due=${stats.due}`);

  // 5. issue #2: reveal answer, then switch filters -> answer must disappear
  const revealed = await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Show answer'));
    if (!b) return false; b.click(); return true;
  })()`, sessionId);
  await sleep(400);
  const answerVisible = await evaluate(`!!document.querySelector('[aria-live="polite"] .text-ink')`, sessionId);
  ok("answer reveals on Show answer", revealed && answerVisible);

  const frontBefore = await evaluate(`document.querySelector('section[aria-label="Flashcard review"] h2')?.textContent`, sessionId);
  // switch to the other filter
  const currentIsDue = await evaluate(`document.querySelector('[aria-label="Filter flashcards"] button')?.getAttribute('aria-pressed')`, sessionId);
  const targetLabel = currentIsDue === "true" ? "All (" : "Due (";
  const switched = await evaluate(`(() => {
    const b = [...document.querySelectorAll('[aria-label="Filter flashcards"] button')]
      .find((x) => x.textContent.includes(${JSON.stringify(targetLabel)}));
    if (!b) return false; b.click(); return true;
  })()`, sessionId);
  await sleep(500);
  const answerGoneAfterSwitch = await evaluate(`!document.querySelector('[aria-live="polite"] .text-ink')`, sessionId);
  const showBtnBack = await evaluate(`!!([...document.querySelectorAll('button')].find((x) => x.textContent.includes('Show answer')))`, sessionId);
  ok("switching filters hides the previous answer", switched && answerGoneAfterSwitch && showBtnBack,
     `switched=${switched} answerHidden=${answerGoneAfterSwitch}`);

  const frontAfter = await evaluate(`document.querySelector('section[aria-label="Flashcard review"] h2')?.textContent`, sessionId);
  ok("answer state does not leak onto another card", answerGoneAfterSwitch || frontBefore === frontAfter,
     `front before: "${frontBefore}" -> after: "${frontAfter}"`);

  // 6. full review round-trip through the UI: reveal + grade, stats must refresh
  const reviewFlow = await evaluate(`(async () => {
    const show = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Show answer'));
    if (!show) return { step: 'no-show-button' };
    show.click();
    await new Promise((r) => setTimeout(r, 300));
    const good = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Good'));
    if (!good) return { step: 'no-quality-button' };
    const before = document.querySelector('[aria-label="Filter flashcards"]')?.textContent;
    good.click();
    await new Promise((r) => setTimeout(r, 1500));
    const notice = document.querySelector('[role="status"]')?.textContent || '';
    const after = document.querySelector('[aria-label="Filter flashcards"]')?.textContent || '';
    return { step: 'done', before, after, notice: notice.slice(0, 120) };
  })()`, sessionId, 25000);
  ok("UI review saves and counters refresh", reviewFlow?.step === "done" && /Review saved/.test(reviewFlow?.notice || ""),
     JSON.stringify(reviewFlow));

  const statsAfter = await (await fetch(`${APP}/api/v1/flashcards/stats`, { headers: { Authorization: `Bearer ${TOKEN}` } })).json();
  ok("server stats unchanged in total (saved cards)", statsAfter.total === stats.total,
     `total ${stats.total} -> ${statsAfter.total}, due ${stats.due} -> ${statsAfter.due}`);

  ok("no console errors on the page", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" || "));
} catch (err) {
  ok("script completed", false, String(err));
} finally {
  try { ws?.close(); } catch { /* ignore */ }
  proc.kill();
  const failed = results.filter((r) => !r.pass).length;
  console.log(`\n== ${results.length - failed}/${results.length} checks passed ==`);
}
