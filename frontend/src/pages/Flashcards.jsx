import CardManager from "../components/CardManager";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  Clock3,
  Layers,
  Plus,
  RefreshCw,
  RotateCcw,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Loading,
} from "../components/ui";
import { api } from "../lib/api";

const QUALITY = [
  { q: 0, label: "Again", hint: "Didn't know it" },
  { q: 1, label: "Hard", hint: "Struggled" },
  { q: 2, label: "Good", hint: "Got it" },
  { q: 3, label: "Easy", hint: "Instant recall" },
];

const dueTime = (iso) =>
  new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(iso) ? iso : `${iso}Z`).getTime();
function dueLabel(iso, now) {
  const diff = dueTime(iso) - now;
  if (diff <= 0) return "Due now";
  if (diff < 3600000)
    return `Due in ${Math.max(1, Math.ceil(diff / 60000))} min`;
  if (diff < 86400000) return `Due in ${Math.ceil(diff / 3600000)} hours`;
  const days = Math.ceil(diff / 86400000);
  return `Due in ${days} ${days === 1 ? "day" : "days"}`;
}

export default function Flashcards() {
  const [offset, setOffset] = useState(0);
  const [cards, setCards] = useState([]);
  const [lectures, setLectures] = useState([]);
  const [stats, setStats] = useState({ total: 0, due: 0, next_due_at: null });
  const [selectedLecture, setSelectedLecture] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generationError, setGenerationError] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [notice, setNotice] = useState("");
  const [generating, setGenerating] = useState(false);
  const [showingAnswer, setShowingAnswer] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewedIds, setReviewedIds] = useState(new Set());
  const [sessionDone, setSessionDone] = useState(0);
  const [view, setView] = useState("due");
  const [now, setNow] = useState(Date.now());
  const reviewLock = useRef(false);

  const load = useCallback(
    async (signal) => {
      setLoading(true);
      setError("");
      try {
        const [deck, totals, library] = await Promise.allSettled([
          api.get(`/flashcards?due=false&offset=${offset}&limit=100`, signal),
          api.get("/flashcards/stats", signal),
          api.get("/lectures", signal),
        ]);
        if (signal?.aborted) return;
        if (deck.status === "rejected") throw deck.reason;
        if (totals.status === "rejected") throw totals.reason;
        setCards(deck.value.items || []);
        setStats(totals.value);
        if (library.status === "fulfilled") {
          const ready = (library.value.items || []).filter(
            (lecture) => lecture.transcript_status === "ready",
          );
          setLectures(ready);
          setSelectedLecture((previous) =>
            ready.some((lecture) => String(lecture.id) === previous)
              ? previous
              : String(ready[0]?.id ?? ""),
          );
        }
        setShowingAnswer(false);
        setReviewedIds(new Set());
        setNow(Date.now());
      } catch (err) {
        if (!signal?.aborted) setError(err.message);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [offset],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      setNow(Date.now());
      api
        .get("/flashcards/stats", controller.signal)
        .then(setStats)
        .catch(() => {});
    }, 60000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  const queue = useMemo(
    () =>
      cards.filter(
        (card) =>
          !reviewedIds.has(card.id) &&
          (view === "all" || dueTime(card.due_at) <= now),
      ),
    [cards, reviewedIds, view, now],
  );
  const current = queue[0] || null;
  const source = lectures.find((lecture) => lecture.id === current?.lecture_id);

  const generate = async (event) => {
    event.preventDefault();
    if (!selectedLecture || generating) return;
    setGenerating(true);
    setGenerationError("");
    setNotice("");
    try {
      const data = await api.post(
        `/lectures/${selectedLecture}/flashcards/generate`,
        { count: Number(count) },
      );
      await load();
      setView(
        data.items.some((card) => dueTime(card.due_at) <= Date.now())
          ? "due"
          : "all",
      );
      setNotice(
        `${data.items.length} ${data.items.length === 1 ? "card is" : "cards are"} ready in your deck. Existing cards keep their review schedule.`,
      );
    } catch (err) {
      setGenerationError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const switchView = (value) => {
    if (reviewLock.current) return;
    setShowingAnswer(false);
    setReviewedIds(new Set());
    setReviewError("");
    setView(value);
  };

  const review = async (quality) => {
    if (!current || !showingAnswer || reviewLock.current) return;
    reviewLock.current = true;
    setReviewing(true);
    setReviewError("");
    try {
      const updated = await api.post(`/flashcards/${current.id}/review`, {
        quality,
      });
      setCards((previous) =>
        previous.map((card) => (card.id === updated.id ? updated : card)),
      );
      setReviewedIds((previous) => new Set([...previous, updated.id]));
      setShowingAnswer(false);
      setSessionDone((value) => value + 1);
      setNow(Date.now());
      setNotice(`Review saved. ${dueLabel(updated.due_at, Date.now())}.`);
      // A saved review stays saved even if refreshing the counters temporarily fails.
      try {
        setStats(await api.get("/flashcards/stats"));
      } catch {
        /* refresh on the next minute */
      }
    } catch (err) {
      setReviewError(
        err.message || "Couldn't save that review. Please try again.",
      );
    } finally {
      reviewLock.current = false;
      setReviewing(false);
    }
  };

  if (loading) return <Loading label="Loading flashcards…" />;
  if (error) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between gap-3 text-xs text-muted">
        <Button
          variant="secondary"
          disabled={offset === 0}
          onClick={() => setOffset((n) => Math.max(0, n - 100))}
        >
          Previous cards
        </Button>
        <span>
          {stats.total
            ? `${offset + 1}–${Math.min(offset + 100, stats.total)} of ${stats.total} cards`
            : "Your card collection"}
        </span>
        <Button
          variant="secondary"
          disabled={offset + 100 >= stats.total}
          onClick={() => setOffset((n) => n + 100)}
        >
          Next cards
        </Button>
      </div>
      <CardManager cards={cards} lectures={lectures} onChange={() => load()} />
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">Spaced repetition</span>
          <h1 className="mt-1 font-display text-3xl font-extrabold sm:text-4xl">
            Flashcards
          </h1>
          <p className="mt-1 text-sm text-muted">
            Recall an idea, check the answer, and plan your next review.
          </p>
        </div>
        <div className="flex gap-2" role="group" aria-label="Filter flashcards">
          <Button
            variant={view === "due" ? "primary" : "secondary"}
            onClick={() => switchView("due")}
            aria-pressed={view === "due"}
            disabled={reviewing}
          >
            Due ({stats.due})
          </Button>
          <Button
            variant={view === "all" ? "primary" : "secondary"}
            onClick={() => switchView("all")}
            aria-pressed={view === "all"}
            disabled={reviewing}
          >
            All ({stats.total})
          </Button>
        </div>
      </header>

      <form
        onSubmit={generate}
        className="card space-y-4 p-5 sm:p-6"
        aria-label="Create flashcards"
      >
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold">
            <Layers size={19} aria-hidden="true" />
            Create cards from a lecture
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-muted">
            Cards use excerpts from your transcript. Choose a lecture with
            captions to get started.
          </p>
        </div>
        {lectures.length ? (
          <>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_100px]">
              <div className="min-w-0">
                <label
                  htmlFor="flashcard-lecture"
                  className="mb-1.5 block text-sm font-bold"
                >
                  Lecture
                </label>
                <select
                  id="flashcard-lecture"
                  className="field truncate text-sm"
                  value={selectedLecture}
                  onChange={(event) => setSelectedLecture(event.target.value)}
                  disabled={generating}
                >
                  {lectures.map((lecture) => (
                    <option value={lecture.id} key={lecture.id}>
                      {lecture.title}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label
                  htmlFor="flashcard-count"
                  className="mb-1.5 block text-sm font-bold"
                >
                  Up to
                </label>
                <select
                  id="flashcard-count"
                  className="field text-sm"
                  value={count}
                  onChange={(event) => setCount(event.target.value)}
                  disabled={generating}
                >
                  {[5, 10, 15, 20].map((value) => (
                    <option key={value} value={value}>
                      {value} cards
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <Button type="submit" loading={generating}>
              <Plus size={17} aria-hidden="true" />
              Generate flashcards
            </Button>
            <p className="text-xs leading-relaxed text-muted">
              Short transcripts may produce fewer cards. Generating again won’t
              duplicate existing cards.
            </p>
          </>
        ) : (
          <p className="rounded-xl bg-sunken p-4 text-sm text-muted">
            No lectures with transcripts are available.{" "}
            <Link to="/library" className="link-underline font-semibold">
              Open your library
            </Link>{" "}
            to add a lecture or upload captions.
          </p>
        )}
        {generationError && (
          <p
            role="alert"
            className="rounded-xl bg-[#fdecec] p-3 text-sm text-danger"
          >
            {generationError}
          </p>
        )}
      </form>

      {notice && (
        <div
          className="rounded-2xl border border-line bg-sage-soft px-5 py-4 text-sm text-sage-ink"
          role="status"
        >
          <p className="font-semibold">{notice}</p>
          {sessionDone > 0 && (
            <p className="mt-1 text-xs">
              {sessionDone} {sessionDone === 1 ? "review" : "reviews"} completed
              this session.
            </p>
          )}
        </div>
      )}
      {stats.total > cards.length && (
        <p className="text-xs text-muted">
          Showing a batch of {cards.length} of your {stats.total} saved cards.
          Refresh to load the next batch after reviewing.
        </p>
      )}

      {!current ? (
        <div className="card">
          <EmptyState
            title={
              view === "due"
                ? "Nothing due right now"
                : sessionDone
                  ? "This review queue is complete"
                  : "No flashcards yet"
            }
            description={
              view === "due"
                ? stats.next_due_at
                  ? `${dueLabel(stats.next_due_at, now)}. You can browse all your saved cards in the meantime.`
                  : "Choose a lecture above to create your first cards."
                : "Generate cards above, or switch filters to browse your saved deck."
            }
            icon={Layers}
            action={
              stats.total > 0 && (
                <Button
                  variant="secondary"
                  onClick={() => (view === "due" ? switchView("all") : load())}
                >
                  {view === "due" ? "Browse all cards" : "Refresh deck"}
                </Button>
              )
            }
          />
        </div>
      ) : (
        <>
          <section
            className="card px-6 py-8 sm:py-10"
            aria-label="Flashcard review"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Badge tone="neutral">{current.topic || "General"}</Badge>
              <span className="text-xs font-semibold text-muted">
                {queue.length} left in this queue
              </span>
            </div>
            {source && (
              <Link
                to={`/lecture/${source.id}`}
                className="mt-3 block truncate text-xs text-muted underline decoration-line2 underline-offset-4"
              >
                {source.title}
              </Link>
            )}
            <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
              <Clock3 size={13} aria-hidden="true" />
              {dueLabel(current.due_at, now)}
            </p>
            <h2
              className="mt-7 text-center font-display text-2xl leading-snug font-bold sm:text-3xl"
              style={{ overflowWrap: "anywhere" }}
            >
              {current.front}
            </h2>
            <div className="mt-6 border-t border-line pt-6" aria-live="polite">
              {showingAnswer ? (
                <div>
                  <p className="mb-2 text-center text-xs font-semibold uppercase tracking-wider text-muted">
                    From the transcript
                  </p>
                  <p
                    className="text-center text-base leading-relaxed text-ink"
                    style={{ overflowWrap: "anywhere" }}
                  >
                    {current.back}
                  </p>
                </div>
              ) : (
                <p className="text-center text-sm text-muted">
                  Try answering from memory before revealing the back.
                </p>
              )}
            </div>
            <div className="mt-7">
              {!showingAnswer ? (
                <Button
                  size="lg"
                  className="w-full"
                  onClick={() => setShowingAnswer(true)}
                >
                  <RotateCcw size={19} aria-hidden="true" />
                  Show answer
                </Button>
              ) : (
                <div>
                  <p className="mb-3 text-center text-sm font-semibold">
                    How well did you remember?
                  </p>
                  <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                    {QUALITY.map(({ q, label, hint }) => (
                      <button
                        key={q}
                        type="button"
                        disabled={reviewing}
                        onClick={() => review(q)}
                        className={`flex min-h-[84px] flex-col items-center justify-center rounded-2xl border px-2 py-3 transition-colors disabled:opacity-60 ${q < 2 ? "border-line bg-coral-soft text-coral-dark hover:border-coral" : "border-line bg-sage-soft text-sage-ink hover:border-sage"}`}
                      >
                        {q < 2 ? (
                          <X size={16} aria-hidden="true" />
                        ) : (
                          <Check size={16} aria-hidden="true" />
                        )}
                        <span className="mt-1 text-sm font-bold">{label}</span>
                        <span className="text-[11px] opacity-80">{hint}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {reviewing && (
              <p role="status" className="mt-3 text-center text-xs text-muted">
                Saving your review…
              </p>
            )}
            {reviewError && (
              <p
                role="alert"
                className="mt-4 rounded-xl bg-[#fdecec] p-3 text-sm text-danger"
              >
                {reviewError}
              </p>
            )}
          </section>
          <p className="text-center text-xs leading-relaxed text-muted">
            Again and Hard are scheduled in 10 minutes. Good and Easy start at
            one day; later successful reviews get longer intervals.
          </p>
        </>
      )}
    </div>
  );
}
