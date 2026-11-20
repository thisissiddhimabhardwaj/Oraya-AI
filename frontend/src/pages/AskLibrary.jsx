import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpen,
  Mic,
  MicOff,
  Search,
  Send,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Badge, Button, Markdown, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { lectureLink } from "../lib/format";
import { listen, speak, stopSpeaking, voiceSupport } from "../lib/voice";

function Sources({ sources }) {
  if (!sources?.length) return null;
  return (
    <ul className="mt-3 space-y-2" aria-label="Sources from your library">
      {sources.map((s) => (
        <li
          key={s.id}
          className="rounded-xl border border-line bg-surface2 p-3 text-sm"
        >
          <Link
            to={lectureLink(s.lecture_id, s.start)}
            className="font-semibold text-forest underline-offset-2 hover:underline"
          >
            <span className="mr-1.5 inline-block rounded bg-forest px-1.5 text-xs text-white">
              {s.id}
            </span>
            {s.lecture_title} · {s.timestamp}
          </Link>
          <p className="mt-1 text-muted">“{s.quote}”</p>
        </li>
      ))}
    </ul>
  );
}

export default function AskLibrary() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speakOn, setSpeakOn] = useState(false);
  const [rate, setRate] = useState(1);
  const [voiceError, setVoiceError] = useState("");
  const [lectures, setLectures] = useState([]);
  const [scope, setScope] = useState("");
  const [keyword, setKeyword] = useState({
    q: "",
    items: null,
    busy: false,
    error: "",
  });
  const stopRef = useRef(null);
  const endRef = useRef(null);
  const speakRef = useRef({ on: false, rate: 1 });
  speakRef.current = { on: speakOn, rate };

  useEffect(() => {
    api
      .get("/library/conversations")
      .then((r) =>
        setMessages(
          r.items.flatMap((x) => [
            { role: "user", content: x.question },
            {
              role: "assistant",
              content: x.answer,
              sources: x.sources,
              mode: x.mode,
              grounded: true,
            },
          ]),
        ),
      )
      .catch(() => {});
    api
      .get("/lectures")
      .then((r) =>
        setLectures(
          (r.items || []).filter((l) => l.transcript_status === "ready"),
        ),
      )
      .catch(() => {});
    return () => {
      stopRef.current?.();
      stopSpeaking();
    };
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, busy]);

  const ask = async (text) => {
    const question = text.trim();
    if (!question || busy) return;
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api.post("/library/ask", {
        question,
        history,
        lecture_ids: scope ? [Number(scope)] : null,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: r.answer,
          sources: r.sources,
          grounded: r.grounded,
          mode: r.mode,
          notice: r.notice,
        },
      ]);
      if (speakRef.current.on) speak(r.answer, { rate: speakRef.current.rate });
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: e.message, error: true },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = () => {
    setVoiceError("");
    if (listening) return stopRef.current?.();
    stopSpeaking();
    setListening(true);
    stopRef.current = listen({
      onInterim: setInput,
      onFinal: (t) => ask(t),
      onError: setVoiceError,
      onEnd: () => setListening(false),
    });
  };

  const runKeyword = async (e) => {
    e.preventDefault();
    if (keyword.q.trim().length < 2) return;
    setKeyword((k) => ({ ...k, busy: true, error: "" }));
    try {
      const r = await api.get(
        `/library/search?q=${encodeURIComponent(keyword.q.trim())}`,
      );
      setKeyword((k) => ({ ...k, items: r.items, busy: false }));
    } catch (err) {
      setKeyword((k) => ({ ...k, busy: false, error: err.message }));
    }
  };

  return (
    <div className="grid gap-8 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <span className="eyebrow">Learn · Ask My Library</span>
        <h1 className="mt-1 font-display text-4xl sm:text-5xl">
          Ask everything you’ve watched
        </h1>
        <p className="mt-2 max-w-xl text-muted">
          Answers come only from your own lecture transcripts, with the exact
          moment cited. If your library doesn’t cover a question, it says so
          instead of guessing.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <label htmlFor="scope" className="text-sm font-semibold">
            Search in
          </label>
          <select
            id="scope"
            className="field !min-h-10 max-w-xs py-1"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="">All my lectures</option>
            {lectures.map((l) => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </select>
        </div>

        <div className="card mt-4 flex min-h-[22rem] flex-col">
          <div
            className="flex-1 space-y-5 overflow-y-auto p-5"
            aria-live="polite"
            aria-label="Conversation"
          >
            {messages.length === 0 && (
              <p className="text-sm text-muted">
                Try “What is inertia?” or “How are force and acceleration
                related?”. Use the microphone to ask out loud.
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[85%] rounded-2xl bg-forest px-4 py-2.5 text-white"
                    : "max-w-[95%]"
                }
              >
                {m.role === "user" ? (
                  m.content
                ) : (
                  <>
                    <div className="mb-1.5 flex flex-wrap gap-2">
                      {m.error ? (
                        <Badge tone="danger">Error</Badge>
                      ) : m.grounded ? (
                        <Badge tone="sage">From your lectures</Badge>
                      ) : (
                        <Badge tone="warn">Not in your library</Badge>
                      )}
                      {m.mode === "demo" && !m.error && (
                        <Badge>Excerpts only</Badge>
                      )}
                    </div>
                    <Markdown text={m.content} />
                    {m.notice && (
                      <p className="mt-2 text-xs text-muted">{m.notice}</p>
                    )}
                    <Sources sources={m.sources} />
                  </>
                )}
              </div>
            ))}
            {busy && (
              <p
                className="flex items-center gap-2 text-sm text-muted"
                role="status"
              >
                <Spinner />
                Searching your lectures…
              </p>
            )}
            <div ref={endRef} />
          </div>

          <form
            className="border-t border-line p-3"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <div className="flex items-center gap-2">
              <label htmlFor="ask-input" className="sr-only">
                Your question
              </label>
              <input
                id="ask-input"
                className="field"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  listening
                    ? "Listening…"
                    : "Ask about anything in your lectures"
                }
                maxLength={1000}
              />
              <Button
                variant={listening ? "primary" : "secondary"}
                onClick={toggleMic}
                aria-pressed={listening}
                disabled={!voiceSupport.listen}
                aria-label={listening ? "Stop listening" : "Ask by voice"}
                title={
                  voiceSupport.listen
                    ? undefined
                    : "Voice input isn't supported in this browser"
                }
              >
                {listening ? (
                  <MicOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Mic className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
              <Button
                type="submit"
                disabled={!input.trim() || busy}
                aria-label="Send question"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm">
              <button
                type="button"
                aria-pressed={speakOn}
                disabled={!voiceSupport.speak}
                onClick={() => {
                  setSpeakOn((v) => !v);
                  stopSpeaking();
                }}
                className="inline-flex items-center gap-1.5 font-semibold text-muted hover:text-ink disabled:opacity-50"
              >
                {speakOn ? (
                  <Volume2 className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <VolumeX className="h-4 w-4" aria-hidden="true" />
                )}
                Spoken answers {speakOn ? "on" : "off"}
              </button>
              {speakOn && (
                <label className="inline-flex items-center gap-2 text-muted">
                  Speed
                  <input
                    type="range"
                    min="0.7"
                    max="1.6"
                    step="0.1"
                    value={rate}
                    onChange={(e) => setRate(Number(e.target.value))}
                    aria-valuetext={`${rate}×`}
                  />
                  <span className="tabular-nums">{rate.toFixed(1)}×</span>
                </label>
              )}
              {!voiceSupport.listen && (
                <span className="text-xs text-muted">
                  Voice input isn’t available in this browser.
                </span>
              )}
            </div>
            {voiceError && (
              <p role="alert" className="mt-2 text-sm font-medium text-danger">
                {voiceError}
              </p>
            )}
          </form>
        </div>
      </div>

      <aside className="lg:col-span-2" aria-labelledby="kw-h">
        <h2 id="kw-h" className="font-display text-2xl">
          Search spoken words
        </h2>
        <p className="mt-1 text-sm text-muted">
          Exact-phrase search across every transcript. No AI involved.
        </p>
        <form onSubmit={runKeyword} className="relative mt-4">
          <Search
            className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <label htmlFor="kw" className="sr-only">
            Search transcripts
          </label>
          <input
            id="kw"
            type="search"
            className="field pl-10"
            placeholder="e.g. net force"
            value={keyword.q}
            onChange={(e) => setKeyword({ ...keyword, q: e.target.value })}
          />
        </form>
        {keyword.error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {keyword.error}
          </p>
        )}
        {keyword.busy && (
          <p className="mt-3 flex items-center gap-2 text-sm text-muted">
            <Spinner />
            Searching…
          </p>
        )}
        {keyword.items &&
          !keyword.busy &&
          (keyword.items.length === 0 ? (
            <p className="mt-4 text-sm text-muted">
              No lecture mentions “{keyword.q}”.
            </p>
          ) : (
            <ul
              className="mt-4 divide-y divide-line"
              aria-label="Transcript matches"
            >
              {keyword.items.map((h, i) => (
                <li key={i} className="py-3">
                  <Link
                    to={lectureLink(h.lecture_id, h.start)}
                    className="text-sm font-semibold text-forest hover:underline"
                  >
                    <BookOpen
                      className="mr-1 inline h-3.5 w-3.5"
                      aria-hidden="true"
                    />
                    {h.lecture_title} · {h.timestamp}
                  </Link>
                  <p className="mt-0.5 text-sm text-muted">{h.text}</p>
                </li>
              ))}
            </ul>
          ))}
      </aside>
    </div>
  );
}
