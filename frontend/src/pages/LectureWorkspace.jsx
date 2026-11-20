import SourceHighlights, {
  HighlightedText,
} from "../components/SourceHighlights";
import PassageTools from "../components/PassageTools";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowUp,
  Bookmark,
  BookOpen,
  CheckCircle2,
  Clapperboard,
  Download,
  FileText,
  Layers,
  ListOrdered,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { VideoPlayer } from "../components/VideoPlayer";
import { ExplainerPanel } from "../components/ExplainerPanel";
import {
  Badge,
  Button,
  Chip,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  Markdown,
  ProgressBar,
} from "../components/ui";
import { api } from "../lib/api";

/* ------------------------------------------------------------------ helpers */
const fmtTs = (sec) => {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
};

const TABS = [
  { id: "tutor", label: "Tutor", icon: MessageSquare },
  { id: "notes", label: "Notes", icon: FileText },
  { id: "quiz", label: "Quiz", icon: ListOrdered },
  { id: "explainer", label: "Explainer", icon: Clapperboard },
];

/* =================================================================== transcript */
function TranscriptPanel({
  lecture,
  transcript,
  onSeek,
  refreshTranscript,
  currentTime,
  onSelectPassage,
}) {
  const [selection, setSelection] = useState("");
  const [highlights, setHighlights] = useState([]);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState(null); // null = not searching
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [bookmarks, setBookmarks] = useState([]);
  const [bmLabel, setBmLabel] = useState("");
  const [bmError, setBmError] = useState("");
  const [showBookmarks, setShowBookmarks] = useState(false);
  const fileRef = useRef(null);

  const loadBookmarks = useCallback(async () => {
    try {
      const data = await api.get(`/lectures/${lecture.id}/bookmarks`);
      setBookmarks(data.items || []);
    } catch {
      /* non-fatal */
    }
  }, [lecture.id]);

  useEffect(() => {
    loadBookmarks();
  }, [loadBookmarks]);

  const runSearch = async (e) => {
    e?.preventDefault();
    const q = query.trim();
    if (!q) {
      setHits(null);
      return;
    }
    setSearching(true);
    setSearchError("");
    try {
      const data = await api.post(`/lectures/${lecture.id}/transcript/search`, {
        q,
      });
      setHits(data.items || []);
    } catch (err) {
      setSearchError(err.message);
      setHits([]);
    } finally {
      setSearching(false);
    }
  };

  const uploadFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setSearchError("");
    try {
      await api.upload(`/lectures/${lecture.id}/transcript`, file);
      await refreshTranscript();
    } catch (err) {
      setBmError(err.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const addBookmark = async (e) => {
    e.preventDefault();
    setBmError("");
    try {
      await api.post(`/lectures/${lecture.id}/bookmarks`, {
        ts: window.__orayaNow?.() ?? 0,
        label: bmLabel.trim(),
      });
      setBmLabel("");
      loadBookmarks();
      setShowBookmarks(true);
    } catch (err) {
      setBmError(err.message);
    }
  };

  const removeBookmark = async (bm) => {
    try {
      await api.del(`/lectures/bookmarks/${bm.id}`);
      setBookmarks((prev) => prev.filter((b) => b.id !== bm.id));
    } catch (err) {
      window.alert(err.message || "Couldn't delete bookmark");
    }
  };

  const segments = transcript?.segments || [];
  const chapters = transcript?.chapters || [];

  return (
    <div className="card flex min-h-0 flex-col overflow-hidden">
      {/* header */}
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-bold">
          <BookOpen className="h-4 w-4 text-coral" aria-hidden="true" />
          Transcript
          {transcript?.source === "sample" && (
            <Badge tone="sage">Sample content</Badge>
          )}
          {transcript?.timed === false && <Badge tone="warn">Untimed</Badge>}
        </h2>
        <button
          type="button"
          onClick={() => setShowBookmarks((v) => !v)}
          className="link-underline text-xs font-bold"
          aria-expanded={showBookmarks}
        >
          Bookmarks ({bookmarks.length})
        </button>
      </div>

      {/* search */}
      <form onSubmit={runSearch} className="border-b border-line px-4 py-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <label htmlFor={`tsearch-${lecture.id}`} className="sr-only">
            Search the transcript
          </label>
          <input
            id={`tsearch-${lecture.id}`}
            type="search"
            className="field min-h-[42px] py-1.5 pl-9 text-sm"
            placeholder="Search the transcript…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (!e.target.value) setHits(null);
            }}
          />
        </div>
        {searchError && (
          <p role="alert" className="mt-2 text-xs font-medium text-danger">
            {searchError}
          </p>
        )}
      </form>

      {/* bookmarks drawer */}
      {showBookmarks && (
        <div className="border-b border-line bg-surface2 px-4 py-3">
          <form onSubmit={addBookmark} className="flex gap-2">
            <label htmlFor={`bm-${lecture.id}`} className="sr-only">
              Bookmark label
            </label>
            <input
              id={`bm-${lecture.id}`}
              className="field min-h-[40px] flex-1 py-1.5 text-sm"
              placeholder="Label at current time…"
              value={bmLabel}
              maxLength={80}
              onChange={(e) => setBmLabel(e.target.value)}
            />
            <Button type="submit" className="min-h-[40px] px-3">
              <Bookmark className="h-4 w-4" aria-hidden="true" />
              Save
            </Button>
          </form>
          {bmError && (
            <p role="alert" className="mt-2 text-xs font-medium text-danger">
              {bmError}
            </p>
          )}
          <ul className="mt-3 space-y-1.5">
            {bookmarks.length === 0 && (
              <li className="text-xs text-muted">
                No bookmarks yet — they're per lecture.
              </li>
            )}
            {bookmarks.map((bm) => (
              <li key={bm.id} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onSeek(bm.ts)}
                  className="flex min-h-[36px] flex-1 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-left text-xs font-semibold transition-colors hover:border-coral"
                >
                  <span className="text-coral">{fmtTs(bm.ts)}</span>
                  <span className="truncate text-muted">
                    {bm.label || "Bookmark"}
                  </span>
                </button>
                <button
                  type="button"
                  aria-label={`Delete bookmark ${bm.label || fmtTs(bm.ts)}`}
                  onClick={() => removeBookmark(bm)}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-[#fdecec] hover:text-danger"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* body */}
      <div
        onMouseUp={() => {
          const text = window.getSelection()?.toString().trim();
          if (text) {
            setSelection(text.slice(0, 6000));
            onSelectPassage?.(text.slice(0, 1000));
          }
        }}
        className="min-h-0 flex-1 overflow-y-auto px-2 py-3"
        style={{ maxHeight: "46vh" }}
      >
        {segments.length === 0 ? (
          <div className="px-2">
            <EmptyState
              title="No transcript yet"
              description="Some videos have captions disabled. Upload an .srt, .vtt or .txt file and the whole workspace comes alive."
              icon={Upload}
              action={
                <Button
                  variant="secondary"
                  loading={uploading}
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="h-4 w-4" aria-hidden="true" />
                  Upload captions
                </Button>
              }
            />
            <input
              ref={fileRef}
              type="file"
              accept=".srt,.vtt,.txt"
              className="sr-only"
              onChange={(e) => uploadFile(e.target.files?.[0])}
              aria-label="Transcript file"
            />
          </div>
        ) : hits !== null ? (
          /* search results */
          <div className="px-2">
            <p
              className="px-2 pb-2 text-xs font-semibold text-muted"
              role="status"
            >
              {searching
                ? "Searching…"
                : `${hits.length} match${hits.length === 1 ? "" : "es"}`}
            </p>
            {hits.length === 0 && !searching && (
              <p className="px-2 text-sm text-muted">
                Nothing matches “{query}”. Try different words.
              </p>
            )}
            <ul className="space-y-2">
              {hits.map((h) => (
                <li key={h.segment_id}>
                  <button
                    type="button"
                    onClick={() => onSeek(h.start)}
                    className="w-full rounded-xl border border-line bg-surface2 p-3 text-left transition-colors hover:border-coral"
                  >
                    <span className="text-xs font-bold text-coral">
                      {transcript?.timed === false
                        ? "Source excerpt"
                        : fmtTs(h.start)}
                    </span>
                    <p className="mt-1 line-clamp-3 text-sm text-ink">
                      {h.text}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
            <Button
              variant="ghost"
              className="mt-3 w-full text-sm"
              onClick={() => {
                setQuery("");
                setHits(null);
              }}
            >
              Back to full transcript
            </Button>
          </div>
        ) : (
          /* full transcript grouped by chapter */
          <div className="space-y-1">
            {chapters.map((ch) => {
              const from = ch.start;
              const next =
                chapters.find((c) => c.idx > ch.idx)?.start ?? Infinity;
              const rows = segments.filter(
                (s) => s.start >= from && s.start < next,
              );
              if (!rows.length) return null;
              return (
                <section key={ch.id} className="mb-3">
                  <button
                    type="button"
                    onClick={() => onSeek(ch.start)}
                    className="mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-surface2"
                  >
                    <span className="text-xs font-bold text-coral">
                      {transcript?.timed === false ? "§" : fmtTs(ch.start)}
                    </span>
                    <span className="text-xs font-bold text-ink">
                      {ch.title}
                    </span>
                  </button>
                  <ul>
                    {rows.map((seg) => (
                      <li key={seg.id}>
                        <button
                          type="button"
                          onClick={() => onSeek(seg.start)}
                          aria-current={
                            transcript?.timed &&
                            currentTime >= seg.start &&
                            currentTime < seg.end
                              ? "true"
                              : undefined
                          }
                          className={`transcript-segment flex w-full gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-coral-soft ${transcript?.timed && currentTime >= seg.start && currentTime < seg.end ? "segment-active" : ""}`}
                        >
                          <span className="w-11 shrink-0 pt-0.5 text-[11px] font-bold text-muted">
                            {transcript?.timed === false
                              ? ""
                              : fmtTs(seg.start)}
                          </span>
                          <span className="text-sm leading-relaxed text-ink">
                            <HighlightedText
                              text={seg.text}
                              highlights={highlights}
                            />
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        )}
      </div>

      <SourceHighlights
        lecture={lecture}
        selection={selection}
        onChange={setHighlights}
      />
      <PassageTools
        lecture={lecture}
        selection={selection}
        timestamp={currentTime}
      />
      {/* footer / upload */}
      <div className="border-t border-line px-4 py-3">
        <input
          ref={fileRef}
          type="file"
          accept=".srt,.vtt,.txt"
          className="sr-only"
          onChange={(e) => uploadFile(e.target.files?.[0])}
          aria-label="Transcript file"
        />
        <button
          type="button"
          className="link-underline inline-flex items-center gap-1.5 text-xs font-bold"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? (
            <RefreshCw
              className="h-3.5 w-3.5 animate-spin"
              aria-hidden="true"
            />
          ) : (
            <Upload className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {uploading
            ? "Importing…"
            : "Replace / upload captions (.srt, .vtt, .txt)"}
        </button>
      </div>
    </div>
  );
}

/* ====================================================================== tutor */
function TutorTab({ lecture, onSeek, selectedText, onClearSelection }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [hist, sugg] = await Promise.all([
          lecture.source === "document"
            ? api.get("/library/conversations").then((r) => ({
                items: r.items
                  .filter((x) =>
                    x.sources?.some((s) => s.lecture_id === lecture.id),
                  )
                  .flatMap((x) => [
                    { id: `u-${x.id}`, role: "user", content: x.question },
                    {
                      id: `a-${x.id}`,
                      role: "assistant",
                      content: x.answer,
                      refs: [],
                      mode: x.mode,
                    },
                  ]),
              }))
            : api.get(`/lectures/${lecture.id}/tutor/messages`),
          api.get(`/lectures/${lecture.id}/tutor/suggestions`),
        ]);
        if (cancelled) return;
        setMessages(hist.items || []);
        setSuggestions(sugg.items || []);
      } catch {
        /* chat history is optional */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lecture.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, sending]);

  const ask = async (text) => {
    const baseQuestion = (text ?? input).trim();
    const question = (
      baseQuestion +
      (selectedText ? `\nSelected source passage: ${selectedText}` : "")
    ).slice(0, 2000);
    if (!question || sending) return;
    setInput("");
    setError("");
    setSending(true);
    const optimisticId = `tmp-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: optimisticId, role: "user", content: question, refs: [] },
    ]);
    try {
      const history = messages
        .filter((m) => m.role === "user" || m.mode === "gemini" || m.mode === "ollama")
        .slice(-12)
        .map((m) => ({ role: m.role, content: m.content }));
      const raw =
        lecture.source === "document"
          ? await api.post("/library/ask", {
              question,
              history,
              lecture_ids: [lecture.id],
            })
          : await api.post(`/lectures/${lecture.id}/tutor/ask`, {
              question,
              history,
            });
      const data =
        lecture.source === "document"
          ? {
              ...raw,
              references: [],
              notice: raw.sources
                ?.map((s) => `${s.id}: ${s.timestamp}`)
                .join(" · "),
            }
          : raw;
      setMessages((prev) => [
        ...prev,
        {
          id: `ans-${Date.now()}`,
          role: "assistant",
          content: data.answer,
          refs: data.references || [],
          mode: data.mode,
          notice: data.notice,
        },
      ]);
    } catch (err) {
      setError(err.message);
      // drop the optimistic user message so the retry is clean
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      setInput(question);
    } finally {
      setSending(false);
    }
  };

  if (lecture.transcript_status !== "ready") {
    return (
      <div className="card">
        <EmptyState
          title="Tutor needs a transcript"
          description="Upload captions in the transcript panel and the tutor can answer with real citations."
          icon={MessageSquare}
        />
      </div>
    );
  }

  return (
    <div className="card flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-bold">
          <MessageSquare className="h-4 w-4 text-coral" aria-hidden="true" />
          AI Tutor
        </h2>
        <Badge tone="info">
          {lecture.source === "document"
            ? "Answers cite source excerpts"
            : "Answers cite timestamps"}
        </Badge>
      </div>

      {selectedText && (
        <div className="selected-source-context">
          <p>Selected passage: {selectedText.slice(0, 150)}…</p>
          <button onClick={onClearSelection}>Clear context</button>
        </div>
      )}
      <div className="tutor-explanation-modes" aria-label="Explanation style">
        {[
          "Explain simply",
          "Use an analogy",
          "Practical example",
          "Step by step",
          "Mathematical explanation",
          "Advanced explanation",
        ].map((mode) => (
          <button
            key={mode}
            disabled={sending}
            onClick={() => {
              const prior = [...messages]
                .reverse()
                .find(
                  (m) =>
                    m.role === "user" &&
                    !/^(Explain simply|Use an analogy|Practical example|Step by step|Mathematical explanation|Advanced explanation):/.test(
                      m.content,
                    ),
                );
              ask(
                `${mode}: ${prior?.content || lecture.title}. Use only supported source material and preserve the original question.`,
              );
            }}
          >
            {mode}
          </button>
        ))}
      </div>
      <div
        ref={scrollRef}
        className="min-h-[320px] flex-1 space-y-4 overflow-y-auto px-4 py-4"
        style={{ maxHeight: "52vh" }}
        aria-live="polite"
      >
        {messages.length === 0 && (
          <div className="rounded-2xl bg-coral-soft p-4">
            <p className="text-sm font-bold text-coral-dark">
              Ask anything about this lecture
            </p>
            <p className="mt-1 text-sm leading-relaxed text-ink/80">
              Answers use your source material. Citations point to real
              passages, never invented evidence.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[92%] rounded-2xl px-5 py-3.5 transition-all duration-200 ${
                m.role === "user"
                  ? "bg-forest text-white shadow-sm ml-auto"
                  : "glass-surface border border-line/80 text-ink shadow-sm"
              }`}
            >
              {m.role === "assistant" ? (
                <Markdown text={m.content} />
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</p>
              )}

              {m.role === "assistant" && (
                <div className="mt-3 flex items-center justify-between border-t border-line/60 pt-2 text-xs">
                  <button
                    type="button"
                    className="font-medium text-forest hover:text-coral transition-colors underline"
                    onClick={async () => {
                      try {
                        await api.post("/memory", {
                          title: `Explanation: ${lecture.title}`.slice(0, 200),
                          kind: "explanation",
                          data: {
                            content: m.content,
                            lecture_id: lecture.id,
                            refs: m.refs,
                          },
                        });
                        setError("Explanation saved in your learning profile.");
                      } catch (e) {
                        setError(e.message);
                      }
                    }}
                  >
                    Save to memory
                  </button>
                  <span className="text-[11px] font-medium text-muted">
                    {m.mode === "gemini" && "AI Tutor · Gemini cloud"}
                    {m.mode === "ollama" && "AI Tutor · Local Qwen 4B"}
                    {m.mode === "demo" && "Transcript excerpts"}
                  </span>
                </div>
              )}
              {m.role === "assistant" && m.refs?.length > 0 && (
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                    Sources:
                  </span>
                  {m.refs.map((r, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => onSeek(r.start)}
                      className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-[11px] font-semibold text-forest transition-colors hover:border-coral hover:text-coral"
                    >
                      {fmtTs(r.start)}
                    </button>
                  ))}
                </div>
              )}
              {m.mode === "demo" && m.role === "assistant" && (
                <p className="mt-2 text-xs leading-relaxed text-muted/90">
                  {m.notice ||
                    "Transcript-only reply · live AI explanation unavailable"}
                </p>
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="glass-surface flex items-center gap-3 rounded-2xl border border-line/80 px-5 py-3.5 text-xs text-muted shadow-sm">
              <div className="typing-indicator" aria-label="Thinking">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
              <span>Searching transcript excerpts and generating verified answer…</span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-center justify-between border-t border-line bg-[#fdecec] px-4 py-2.5 text-xs font-medium text-danger"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => ask()}
            className="ml-3 font-semibold underline hover:text-danger/80"
          >
            Retry
          </button>
        </div>
      )}

      {suggestions.length > 0 && messages.length < 3 && (
        <div className="flex flex-wrap gap-2 border-t border-line px-4 py-3">
          {suggestions.slice(0, 4).map((s) => (
            <Chip
              key={s}
              onClick={() => ask(s)}
              className="min-h-[36px] px-3 py-1 text-xs"
            >
              {s}
            </Chip>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
        className="flex items-end gap-2 border-t border-line px-4 py-3"
      >
        <label htmlFor="tutor-input" className="sr-only">
          Ask the tutor
        </label>
        <textarea
          id="tutor-input"
          rows={1}
          className="field max-h-32 min-h-[44px] flex-1 resize-none py-2.5 text-sm"
          placeholder="Ask about this video or follow up on an answer…"
          value={input}
          maxLength={2000}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask();
            }
          }}
        />
        <Button
          type="submit"
          disabled={!input.trim()}
          loading={sending}
          className="min-h-[44px] px-3"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only sm:not-sr-only">Send</span>
        </Button>
      </form>
    </div>
  );
}

/* ====================================================================== notes */
function NotesTab({ lecture, onSeek }) {
  const [editingNote, setEditingNote] = useState(null);
  const [notes, setNotes] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [generating, setGenerating] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(`/lectures/${lecture.id}/notes`);
      setNotes(data.items || []);
      setActiveId((prev) => prev ?? data.items?.[0]?.id ?? null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [lecture.id]);

  useEffect(() => {
    load();
    window.addEventListener("oraya:notes-changed", load);
    return () => window.removeEventListener("oraya:notes-changed", load);
  }, [load]);

  const generate = async (kind) => {
    setGenerating(kind);
    setError("");
    try {
      const note = await api.post(`/lectures/${lecture.id}/notes/generate`, {
        kind,
      });
      setNotes((prev) => [note, ...prev.filter((n) => n.kind !== kind)]);
      setActiveId(note.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating("");
    }
  };

  const remove = async (note) => {
    if (!window.confirm("Delete this note?")) return;
    try {
      await api.del(`/notes/${note.id}`);
      setNotes((prev) => prev.filter((n) => n.id !== note.id));
      if (activeId === note.id) setActiveId(null);
    } catch (err) {
      window.alert(err.message || "Couldn't delete note");
    }
  };

  const active = notes.find((n) => n.id === activeId) || null;

  if (lecture.transcript_status !== "ready") {
    return (
      <div className="card">
        <EmptyState
          title="Notes need a transcript"
          description="Upload captions first — notes are generated strictly from what the lecture says."
          icon={FileText}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {[
          { kind: "summary", label: "Summary", icon: Sparkles },
          { kind: "chapters", label: "Chapter notes", icon: ListOrdered },
          { kind: "definitions", label: "Definitions", icon: BookOpen },
        ].map(({ kind, label, icon: Icon }) => (
          <Button
            key={kind}
            variant="secondary"
            loading={generating === kind}
            onClick={() => generate(kind)}
          >
            {!generating && <Icon className="h-4 w-4" aria-hidden="true" />}
            {label}
          </Button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-sm font-medium text-danger"
        >
          {error}
        </div>
      )}

      {loading ? (
        <Loading label="Loading notes…" />
      ) : notes.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No notes yet"
            description="Generate a summary, chapter-wise notes or a definition list — then edit and export."
            icon={FileText}
          />
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
            {notes.map((n) => (
              <Chip
                key={n.id}
                selected={n.id === activeId}
                onClick={() => setActiveId(n.id)}
                className="min-h-[36px] px-3 py-1 text-xs"
              >
                {n.kind === "summary"
                  ? "Summary"
                  : n.kind === "chapters"
                    ? "Chapters"
                    : n.kind === "manual"
                      ? n.title
                      : "Definitions"}
              </Chip>
            ))}
            {active && (
              <span className="ml-auto flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    api.download(
                      `/notes/${active.id}/export?format=md`,
                      `${active.kind}.md`,
                    )
                  }
                  className="link-underline inline-flex items-center gap-1 text-xs font-bold"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />{" "}
                  Markdown
                </button>
                <button
                  type="button"
                  onClick={() =>
                    api.download(
                      `/notes/${active.id}/export?format=pdf`,
                      `${active.kind}.pdf`,
                    )
                  }
                  className="link-underline inline-flex items-center gap-1 text-xs font-bold"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" /> PDF
                </button>
                <button
                  type="button"
                  aria-label="Delete note"
                  onClick={() => remove(active)}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-[#fdecec] hover:text-danger"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </span>
            )}
          </div>

          {active && (
            <div className="px-5 py-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-bold">{active.title}</h3>
                <Badge tone={active.mode === "gemini" ? "info" : "neutral"}>
                  {active.mode === "gemini"
                    ? "AI generated"
                    : active.mode === "manual"
                      ? "Written by you"
                      : "Transcript excerpts"}
                </Badge>
              </div>
              {editingNote?.id === active.id ? (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      const saved = await api.patch(`/notes/${active.id}`, {
                        title: editingNote.title,
                        content_md: editingNote.content,
                      });
                      setNotes((ns) =>
                        ns.map((n) => (n.id === saved.id ? saved : n)),
                      );
                      setEditingNote(null);
                    } catch (e) {
                      setError(e.message);
                    }
                  }}
                >
                  <label className="studio-label">
                    Title
                    <input
                      className="field"
                      value={editingNote.title}
                      onChange={(e) =>
                        setEditingNote({
                          ...editingNote,
                          title: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="studio-label">
                    Note content
                    <textarea
                      className="field"
                      rows={10}
                      value={editingNote.content}
                      onChange={(e) =>
                        setEditingNote({
                          ...editingNote,
                          content: e.target.value,
                        })
                      }
                    />
                  </label>
                  <div className="flex gap-2">
                    <Button type="submit">Save note</Button>
                    <Button
                      variant="secondary"
                      onClick={() => setEditingNote(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <>
                  <Markdown text={active.content_md} className="text-sm" />
                  <button
                    className="text-xs text-forest underline mt-4"
                    onClick={() =>
                      setEditingNote({
                        id: active.id,
                        title: active.title,
                        content: active.content_md,
                      })
                    }
                  >
                    Edit note
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ======================================================================= quiz */
function QuizTab({ lecture }) {
  const [quiz, setQuiz] = useState(null);
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("mixed");
  const [generating, setGenerating] = useState(false);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const generate = async () => {
    setGenerating(true);
    setError("");
    setResult(null);
    setAnswers({});
    try {
      const data = await api.post(`/lectures/${lecture.id}/quiz/generate`, {
        count,
        difficulty,
      });
      setQuiz(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const submit = async () => {
    if (!quiz) return;
    const payload = quiz.questions.map((q) => ({
      question_id: q.id,
      answer: String(answers[q.id] ?? "").trim(),
    }));
    if (payload.some((a) => !a.answer)) {
      setError("Answer every question before submitting.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const data = await api.post(`/quizzes/${quiz.id}/attempts`, {
        answers: payload,
      });
      setResult(data);
      window.scrollTo?.({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (lecture.transcript_status !== "ready") {
    return (
      <div className="card">
        <EmptyState
          title="Quizzes need a transcript"
          description="Upload captions and ORAYA will build questions from what was actually said."
          icon={ListOrdered}
        />
      </div>
    );
  }

  if (result) {
    const pct = Math.round(result.score * 100);
    return (
      <div className="space-y-4">
        <div className="card p-6 text-center">
          <p className="eyebrow">Your score</p>
          <p className="mt-1 font-display text-5xl font-extrabold">{pct}%</p>
          <p className="mt-1 text-sm text-muted">
            {result.results.filter((r) => r.correct).length} of {result.count}{" "}
            correct
          </p>
          <div className="mx-auto mt-4 max-w-xs">
            <ProgressBar value={pct} label={`Quiz score ${pct}%`} />
          </div>
          {result.gaps.length > 0 && (
            <p className="mx-auto mt-4 max-w-md rounded-xl bg-coral-soft p-3 text-sm font-medium text-coral-dark">
              Knowledge gaps: {result.gaps.join(", ")}
            </p>
          )}
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Button
              onClick={() => {
                setResult(null);
                setQuiz(null);
                setAnswers({});
              }}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              New quiz
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setResult(null);
                setAnswers({});
              }}
            >
              Retake this quiz
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          {result.results.map((r, i) => {
            const q = quiz?.questions.find((x) => x.id === r.question_id);
            return (
              <div
                key={r.question_id}
                className={`card p-5 ${r.correct ? "border-sage" : "border-danger/40"}`}
              >
                <div className="flex items-start gap-3">
                  {r.correct ? (
                    <CheckCircle2
                      className="mt-0.5 h-5 w-5 shrink-0 text-ok"
                      aria-hidden="true"
                    />
                  ) : (
                    <XIcon
                      className="mt-0.5 h-5 w-5 shrink-0 text-danger"
                      aria-hidden="true"
                    />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-bold">
                      {i + 1}. {q?.prompt || "Question"}
                    </p>
                    {!r.correct && (
                      <p className="mt-1.5 text-sm text-muted">
                        Your answer:{" "}
                        <span className="font-semibold text-danger">
                          {String(answers[r.question_id] || "—")}
                        </span>
                      </p>
                    )}
                    <p className="mt-1 text-sm text-ok">
                      Correct:{" "}
                      <span className="font-semibold">{r.correct_answer}</span>
                    </p>
                    {r.explanation && (
                      <p className="mt-2 rounded-xl bg-sunken p-3 text-sm leading-relaxed text-ink">
                        {r.explanation}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge tone="neutral">{r.topic}</Badge>
                      {q?.difficulty && (
                        <Badge tone="info">{q.difficulty}</Badge>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (!quiz) {
    return (
      <div className="card p-6">
        <h2 className="text-lg font-bold">Build a quiz</h2>
        <p className="mt-1 text-sm text-muted">
          Questions are generated from this lecture's transcript — MCQs and
          short answers with instant grading.
        </p>

        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <label
              htmlFor="quiz-count"
              className="mb-2 block text-sm font-bold"
            >
              Questions: {count}
            </label>
            <input
              id="quiz-count"
              type="range"
              min={3}
              max={15}
              step={1}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-full accent-[#E8705B]"
            />
          </div>
          <div>
            <span className="mb-2 block text-sm font-bold">Difficulty</span>
            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="Difficulty"
            >
              {["easy", "medium", "hard", "mixed"].map((d) => (
                <Chip
                  key={d}
                  selected={difficulty === d}
                  onClick={() => setDifficulty(d)}
                  className="min-h-[38px] px-3 py-1 text-xs capitalize"
                >
                  {d}
                </Chip>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-sm font-medium text-danger"
          >
            {error}
          </div>
        )}

        <Button
          className="mt-6"
          size="lg"
          loading={generating}
          onClick={generate}
        >
          {!generating && <Sparkles className="h-5 w-5" aria-hidden="true" />}
          Generate quiz
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">{quiz.lecture_title}</h2>
          <p className="text-xs text-muted">
            {quiz.questions.length} questions · {difficulty} ·{" "}
            {quiz.mode === "gemini" ? "AI generated" : "Transcript fallback"}
          </p>
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            setQuiz(null);
            setAnswers({});
          }}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Start over
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-sm font-medium text-danger"
        >
          {error}
        </div>
      )}

      <ol className="space-y-4">
        {quiz.questions.map((q, i) => (
          <li key={q.id} className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-bold">
                {i + 1}. {q.prompt}
              </p>
              <Badge
                tone={
                  q.difficulty === "hard"
                    ? "danger"
                    : q.difficulty === "easy"
                      ? "ok"
                      : "neutral"
                }
              >
                {q.difficulty}
              </Badge>
            </div>

            {q.type === "mcq" ? (
              <fieldset className="mt-4">
                <legend className="sr-only">Answer for question {i + 1}</legend>
                <div className="space-y-2">
                  {q.options.map((opt) => {
                    const chosen = answers[q.id] === opt;
                    return (
                      <label
                        key={opt}
                        className={`flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl border px-4 py-2.5 text-sm transition-colors ${
                          chosen
                            ? "border-sage bg-sage-soft font-semibold"
                            : "border-line bg-surface hover:border-line2"
                        }`}
                      >
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          value={opt}
                          checked={chosen}
                          onChange={() =>
                            setAnswers((prev) => ({ ...prev, [q.id]: opt }))
                          }
                          className="h-4 w-4 accent-[#2F4A2B]"
                        />
                        {opt}
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ) : (
              <div className="mt-4">
                <label htmlFor={`sa-${q.id}`} className="sr-only">
                  Your answer for question {i + 1}
                </label>
                <textarea
                  id={`sa-${q.id}`}
                  rows={2}
                  className="field resize-y text-sm"
                  placeholder="Answer in your own words…"
                  value={answers[q.id] || ""}
                  onChange={(e) =>
                    setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                  }
                />
              </div>
            )}
          </li>
        ))}
      </ol>

      <div className="flex items-center gap-3">
        <Button size="lg" loading={submitting} onClick={submit}>
          Submit answers
        </Button>
        <span className="text-xs text-muted">
          {Object.values(answers).filter(Boolean).length}/
          {quiz.questions.length} answered
        </span>
      </div>
    </div>
  );
}

function XIcon({ className = "" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

/* ================================================================== explainer */
/* ================================================================= workspace */
export default function LectureWorkspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const lectureId = Number(id);
  // Deep link from Ask My Library: /lecture/12?t=95 opens the video at 1:35.
  const [searchParams] = useSearchParams();
  const deepLinkSeconds = Number(searchParams.get("t")) || 0;

  const [lecture, setLecture] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [startAt, setStartAt] = useState(0);
  const [tab, setTab] = useState("tutor");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const seekRef = useRef(null);
  const [selectedPassage, setSelectedPassage] = useState("");
  const [currentTime, setCurrentTime] = useState(0);
  const currentTimeRef = useRef(0);
  const lastPostedRef = useRef(0);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [detail, tr, prog] = await Promise.all([
        api.get(`/lectures/${lectureId}`),
        api.get(`/lectures/${lectureId}/transcript`).catch(() => null),
        api
          .get(`/lectures/${lectureId}/progress`)
          .catch(() => ({ seconds: 0 })),
      ]);
      setLecture(detail);
      setTranscript(tr);
      setStartAt(
        deepLinkSeconds > 0
          ? deepLinkSeconds
          : (prog.resume_seconds ?? prog.seconds ?? 0),
      );
      lastPostedRef.current = prog.seconds || 0;
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [lectureId, deepLinkSeconds]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // expose current playback time for bookmark capture
  useEffect(() => {
    window.__orayaNow = () => currentTimeRef.current;
    return () => {
      delete window.__orayaNow;
    };
  }, []);

  const refreshTranscript = useCallback(async () => {
    try {
      const tr = await api.get(`/lectures/${lectureId}/transcript`);
      setTranscript(tr);
      setLecture((prev) =>
        prev ? { ...prev, transcript_status: "ready" } : prev,
      );
    } catch (err) {
      window.alert(err.message);
    }
  }, [lectureId]);

  const onTime = useCallback(
    (t) => {
      currentTimeRef.current = t;
      setCurrentTime(Math.floor(t));
      // persist watch progress every ~10 observed seconds (server keeps the max)
      if (Math.abs(t - lastPostedRef.current) >= 10) {
        lastPostedRef.current = t;
        api
          .post(`/lectures/${lectureId}/progress`, { seconds: Math.floor(t) })
          .catch(() => {});
      }
    },
    [lectureId],
  );

  const onSeek = useCallback((seconds) => {
    seekRef.current?.(Number(seconds) || 0);
    // scroll video into view on small screens
    document
      .getElementById("oraya-video")
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  // flush progress when leaving the page
  useEffect(() => {
    const flush = () => {
      const t = currentTimeRef.current;
      if (t > 0 && Math.abs(t - lastPostedRef.current) >= 2) {
        api
          .post(`/lectures/${lectureId}/progress`, { seconds: Math.floor(t) })
          .catch(() => {});
      }
    };
    window.addEventListener("beforeunload", flush);
    return () => {
      flush();
      window.removeEventListener("beforeunload", flush);
    };
  }, [lectureId]);

  const onTabKeyDown = (e) => {
    const idx = TABS.findIndex((t) => t.id === tab);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const next =
        (idx + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
      setTab(TABS[next].id);
      document.getElementById(`tab-${TABS[next].id}`)?.focus();
    }
  };

  const hasVideo = useMemo(
    () =>
      Boolean(lecture && lecture.url && !lecture.video_id.startsWith("doc-")),
    [lecture],
  );

  if (loading) return <Loading label="Opening your workspace…" />;
  if (error) return <ErrorState message={error} onRetry={loadAll} />;
  if (!lecture)
    return (
      <ErrorState
        message="Lecture not found."
        onRetry={() => navigate("/library")}
      />
    );

  return (
    <div className="lecture-studio space-y-5">
      {/* header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => navigate("/library")}
            className="link-underline text-xs font-bold"
          >
            ← Back to library
          </button>
          <h1 className="mt-1.5 font-display text-2xl leading-tight font-extrabold sm:text-3xl">
            {lecture.title}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {lecture.channel && <Badge tone="neutral">{lecture.channel}</Badge>}
            {lecture.source === "sample" && (
              <Badge tone="sage">Bundled sample lecture</Badge>
            )}
            {lecture.source === "upload" && (
              <Badge tone="info">Uploaded transcript</Badge>
            )}
            {transcript?.timed === false && (
              <Badge tone="warn">Untimed transcript</Badge>
            )}
            <Badge tone={lecture.transcript_status === "ready" ? "ok" : "warn"}>
              {lecture.transcript_status === "ready"
                ? "Transcript ready"
                : "No transcript"}
            </Badge>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        {/* left: video + transcript */}
        <div className="space-y-4 lg:col-span-3">
          <div id="oraya-video">
            {hasVideo ? (
              <VideoPlayer
                videoId={lecture.video_id}
                startAt={startAt}
                onTime={onTime}
                seekRef={seekRef}
              />
            ) : (
              <article className="document-reading-preview">
                <div>
                  <span className="eyebrow">YOUR READING STUDIO</span>
                  <span>Source material · Select & explore</span>
                </div>
                <h2>A closer look.</h2>
                {(transcript?.segments || []).slice(0, 2).map((seg) => (
                  <p key={seg.id}>{seg.text}</p>
                ))}
                <small>Your original text. Full source and search below.</small>
              </article>
            )}
          </div>

          <TranscriptPanel
            lecture={lecture}
            transcript={transcript}
            onSeek={onSeek}
            refreshTranscript={refreshTranscript}
            currentTime={currentTime}
            onSelectPassage={setSelectedPassage}
          />
        </div>

        {/* right: tabs */}
        <div className="lg:col-span-2">
          <div
            role="tablist"
            aria-label="Learning tools"
            className="mb-4 flex gap-1 overflow-x-auto rounded-2xl border border-line bg-surface p-1"
          >
            {TABS.map(({ id: tabId, label, icon: Icon }) => (
              <button
                key={tabId}
                id={`tab-${tabId}`}
                type="button"
                role="tab"
                aria-selected={tab === tabId}
                aria-controls={`panel-${tabId}`}
                tabIndex={tab === tabId ? 0 : -1}
                onClick={() => setTab(tabId)}
                onKeyDown={onTabKeyDown}
                className={`flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl px-3 text-sm font-bold whitespace-nowrap transition-colors ${
                  tab === tabId
                    ? "bg-coral text-white"
                    : "text-muted hover:bg-surface2 hover:text-ink"
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>

          {TABS.map((tool) => (
            <div
              key={tool.id}
              id={`panel-${tool.id}`}
              role="tabpanel"
              aria-labelledby={`tab-${tool.id}`}
              hidden={tab !== tool.id}
              tabIndex={0}
              className="focus:outline-none"
            >
              {tool.id === "tutor" && (
                <TutorTab
                  key={lecture.id}
                  lecture={lecture}
                  selectedText={selectedPassage}
                  onClearSelection={() => setSelectedPassage("")}
                  onSeek={onSeek}
                />
              )}
              {tool.id === "notes" && (
                <NotesTab lecture={lecture} onSeek={onSeek} />
              )}
              {tool.id === "quiz" && <QuizTab lecture={lecture} />}
              {tool.id === "explainer" && (
                <ExplainerPanel key={lecture.id} lecture={lecture} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
