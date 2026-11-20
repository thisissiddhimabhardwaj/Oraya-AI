import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  Clapperboard,
  FileText,
  Flame,
  Layers,
  Target,
  TrendingUp,
} from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Loading,
  ProgressBar,
} from "../components/ui";
import { api } from "../lib/api";

function masteryTone(score) {
  if (score >= 0.7) return "ok";
  if (score >= 0.4) return "warn";
  return "danger";
}

function masteryColor(score) {
  if (score >= 0.7) return "bg-sage";
  if (score >= 0.4) return "bg-coral";
  return "bg-danger";
}

function Totals({ totals }) {
  const items = [
    { icon: BookOpen, label: "Lectures", value: totals.lectures ?? 0 },
    { icon: FileText, label: "Notes", value: totals.notes ?? 0 },
    { icon: Target, label: "Quiz attempts", value: totals.quizzes ?? 0 },
    {
      icon: Clapperboard,
      label: "Explainer videos",
      value: totals.videos ?? 0,
    },
    {
      icon: Layers,
      label: "Lecture minutes reached",
      value: totals.minutes_watched ?? 0,
    },
    {
      icon: TrendingUp,
      label: "Average score",
      value: totals.avg_score ? `${Math.round(totals.avg_score * 100)}%` : "—",
    },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map(({ icon: Icon, label, value }) => (
        <div key={label} className="card flex items-center gap-4 p-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sunken text-muted">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-display text-2xl font-extrabold">{value}</p>
            <p className="truncate text-sm text-muted">{label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Progress() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [overview, quizHistory] = await Promise.all([
        api.get("/progress/overview"),
        api.get("/quiz-history"),
      ]);
      setData(overview);
      setHistory(quizHistory.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <Loading label="Crunching your numbers…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data)
    return <ErrorState message="No progress data yet." onRetry={load} />;

  const mastery = data.mastery || [];
  const weak = data.weak_topics || [];
  const recs = data.recommendations || [];
  const totals = data.totals || {};

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">Analytics</span>
          <h1 className="mt-1 font-display text-3xl font-extrabold sm:text-4xl">
            Your progress
          </h1>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-sm font-semibold">
          <Flame className="h-4 w-4 text-coral" aria-hidden="true" />
          {data.streak_days}-day streak
        </div>
      </div>

      <section
        aria-labelledby="mastery-heading"
        className="grid gap-5 lg:grid-cols-3"
      >
        <div className="card p-5 sm:p-6 lg:col-span-2">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="mastery-heading" className="text-lg font-bold">
              Topic mastery
            </h2>
            <p className="text-xs text-muted">From your quiz results</p>
          </div>

          {mastery.length ? (
            <ul className="mt-5 space-y-4">
              {mastery.map((m) => (
                <li key={m.topic}>
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate font-semibold">{m.topic}</span>
                    <span className="flex shrink-0 items-center gap-2">
                      <Badge tone={masteryTone(m.score)}>
                        {Math.round(m.score * 100)}%
                      </Badge>
                      <span className="hidden text-xs text-muted sm:inline">
                        {m.lecture_count} lecture
                        {m.lecture_count === 1 ? "" : "s"}
                      </span>
                    </span>
                  </div>
                  <div className="mt-2">
                    <ProgressBar
                      value={m.score * 100}
                      label={`${m.topic}: ${Math.round(m.score * 100)}% mastery`}
                    />
                  </div>
                  <div
                    className={`mt-1.5 h-1 w-full rounded-full ${masteryColor(m.score)} opacity-30`}
                    aria-hidden="true"
                    style={{ maxWidth: `${Math.max(8, m.score * 100)}%` }}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-4">
              <EmptyState
                title="No mastery data yet"
                description="Take a quiz on any lecture and your topic-by-topic mastery will appear here."
                icon={BarChart3}
                action={
                  <Button
                    variant="secondary"
                    onClick={() => navigate("/library")}
                  >
                    Browse lectures
                  </Button>
                }
              />
            </div>
          )}
        </div>

        <div className="space-y-5">
          <div className="card p-5 sm:p-6">
            <h2 className="text-lg font-bold">Weak spots</h2>
            {weak.length ? (
              <>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {weak.map((t) => (
                    <li key={t}>
                      <Badge tone="danger">{t}</Badge>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-sm text-muted">
                  These topics scored below 60% — revisit the lecture sections
                  that cover them.
                </p>
              </>
            ) : (
              <p className="mt-3 text-sm text-muted">
                {mastery.length
                  ? "No weak topics — you're above 60% everywhere so far."
                  : "Take a quiz to reveal weak spots."}
              </p>
            )}
          </div>

          <div className="card p-5 sm:p-6">
            <h2 className="text-lg font-bold">What to do next</h2>
            <ul className="mt-3 space-y-2.5">
              {recs.map((r) => (
                <li key={r.href + r.label}>
                  <button
                    type="button"
                    onClick={() => navigate(r.href)}
                    className="w-full rounded-xl border border-line bg-surface2 px-4 py-3 text-left text-sm font-semibold transition-colors hover:border-coral"
                  >
                    {r.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section aria-labelledby="totals-heading">
        <h2 id="totals-heading" className="mb-3 text-lg font-bold">
          Totals
        </h2>
        <Totals totals={totals} />
      </section>

      <section aria-labelledby="history-heading">
        <h2 id="history-heading" className="mb-3 text-lg font-bold">
          Quiz history
        </h2>
        {history.length ? (
          <div className="card divide-y divide-line">
            {history.map((h) => (
              <div
                key={h.id}
                className="flex items-center justify-between gap-4 px-5 py-4"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold">
                    {h.lecture_title}
                  </p>
                  <p className="text-xs text-muted">
                    {new Date(h.created_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <Badge
                    tone={
                      h.score >= 0.7 ? "ok" : h.score >= 0.4 ? "warn" : "danger"
                    }
                  >
                    {Math.round(h.score * 100)}%
                  </Badge>
                  <span className="text-xs text-muted">{h.count} Qs</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="card">
            <EmptyState
              title="No quizzes yet"
              description="Generated quizzes and your attempts will be listed here."
              icon={Target}
              action={
                <Button
                  variant="secondary"
                  onClick={() => navigate("/library")}
                >
                  Open a lecture
                </Button>
              }
            />
          </div>
        )}
      </section>
    </div>
  );
}
