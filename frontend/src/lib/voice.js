/** Thin wrappers over the browser's Web Speech API. Support varies by browser, so always feature-detect. */
const Recognition =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

export const voiceSupport = {
  listen: Boolean(Recognition),
  speak: typeof window !== "undefined" && "speechSynthesis" in window,
};

const ERRORS = {
  "not-allowed":
    "Microphone access was blocked. Allow it in your browser's site settings, or type your question.",
  "service-not-allowed":
    "Speech recognition isn't allowed in this browser context. Type your question instead.",
  "no-speech": "I didn't hear anything. Tap the microphone and try again.",
  "audio-capture": "No microphone was found on this device.",
  network: "Speech recognition needs a network connection in this browser.",
};

/** Starts one dictation. Returns stop(). onFinal gets the transcript; onError gets a readable message. */
export function listen({ lang = "en-US", onInterim, onFinal, onError, onEnd }) {
  if (!Recognition) {
    onError?.(
      "Voice input isn't supported in this browser. Chrome, Edge and Safari support it.",
    );
    onEnd?.();
    return () => {};
  }
  const rec = new Recognition();
  rec.lang = lang;
  rec.interimResults = true;
  rec.continuous = false;
  let finalText = "";
  rec.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    onInterim?.((finalText + interim).trim());
  };
  rec.onerror = (e) =>
    onError?.(ERRORS[e.error] || `Voice input failed (${e.error}).`);
  rec.onend = () => {
    if (finalText.trim()) onFinal?.(finalText.trim());
    onEnd?.();
  };
  try {
    rec.start();
  } catch {
    onError?.("Voice input is already running.");
    onEnd?.();
  }
  return () => rec.stop();
}

/** Remove markdown and [S1] / [1:20] citation markers so they aren't read aloud. */
export function speakable(text) {
  return text
    .replace(/\[(?:S\d+|[\d:,;\s–-]+)\]/g, "")
    .replace(/[*_`#>]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function speak(text, { rate = 1, onEnd } = {}) {
  if (!voiceSupport.speak) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(speakable(text));
  u.rate = rate;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export const stopSpeaking = () =>
  voiceSupport.speak && window.speechSynthesis.cancel();
