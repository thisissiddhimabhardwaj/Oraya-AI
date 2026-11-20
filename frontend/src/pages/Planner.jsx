import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, RefreshCw, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Loading,
  ProgressBar,
} from "../components/ui";
import { api } from "../lib/api";
import { lectureLink } from "../lib/format";

const KIND = {
  watch: ["Watch", "info"],
  revise: ["Revise", "sage"],
  practice: ["Practise", "coral"],
};
const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const dayLabel = (iso) => {
  const d = new Date(`${iso}T12:00:00`);
  const diff = Math.round((d - new Date(`${todayIso()}T12:00:00`)) / 86400000);
  const base = d.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "short",
  });
  return diff === 0
    ? `Today · ${base}`
    : diff === 1
      ? `Tomorrow · ${base}`
      : base;
};

function PlanView({ plan, onChange, onDelete }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const days = useMemo(() => {
    const g = {};
    plan.tasks.forEach((t) => (g[t.day] ||= []).push(t));
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [plan.tasks]);

  const toggle = async (t) => {
    setError("");
    try {
      await api.patch(`/planner/tasks/${t.id}`, {
        status: t.status === "done" ? "pending" : "done",
      });
      onChange(await api.get(`/planner/plans/${plan.id}`));
    } catch (e) {
      setError(e.message);
    }
  };
  const reschedule = async () => {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const r = await api.post(`/planner/plans/${plan.id}/reschedule`);
      setNote(
        r.moved
          ? `Moved ${r.moved} missed ${r.moved === 1 ? "task" : "tasks"} onto upcoming days.`
          : "Nothing was overdue.",
      );
      onChange(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const { done, total, overdue } = plan.progress;

  return (
    <section className="card p-5 sm:p-6" aria-labelledby={`plan-${plan.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={`plan-${plan.id}`} className="font-display text-3xl">
            {plan.title}
          </h2>
          <p className="text-sm text-muted">
            Exam{" "}
            {new Date(`${plan.exam_date}T12:00:00`).toLocaleDateString(
              undefined,
              { dateStyle: "long" },
            )}{" "}
            · up to {plan.daily_minutes} min/day
          </p>
        </div>
        <div className="flex gap-2">
          {overdue > 0 && (
            <Button onClick={reschedule} loading={busy}>
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Reschedule {overdue} missed
            </Button>
          )}
          <Button
            variant="secondary"
            disabled={busy}
            onClick={async () => {
              const minutes = window.prompt(
                "Available study minutes per day (15–480)",
                String(plan.daily_minutes),
              );
              if (!minutes) return;
              setBusy(true);
              try {
                onChange(
                  await api.post(`/planner/plans/${plan.id}/recalculate`, {
                    daily_minutes: Number(minutes),
                  }),
                );
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Rebalance plan
          </Button>
          <Button
            variant="ghost"
            className="text-danger"
            aria-label={`Delete plan ${plan.title}`}
            onClick={onDelete}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
      <div className="mt-4 max-w-md">
        <ProgressBar
          value={total ? done / total : 0}
          label={`${done} of ${total} tasks done`}
        />
      </div>
      {note && (
        <p role="status" className="mt-3 text-sm text-ok">
          {note}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      )}

      <ol className="mt-6 space-y-5">
        {days.map(([day, tasks]) => (
          <li key={day}>
            <h3
              className={`text-sm font-bold uppercase tracking-wider ${day < todayIso() && tasks.some((t) => t.status === "pending") ? "text-danger" : "text-muted"}`}
            >
              {dayLabel(day)}
            </h3>
            <ul className="mt-2 divide-y divide-line rounded-xl border border-line">
              {tasks.map((t) => (
                <li
                  key={t.id}
                  className="flex flex-wrap items-center gap-3 px-4 py-3"
                >
                  <input
                    id={`t-${t.id}`}
                    type="checkbox"
                    className="h-5 w-5 accent-[var(--color-forest)]"
                    checked={t.status === "done"}
                    onChange={() => toggle(t)}
                  />
                  <label
                    htmlFor={`t-${t.id}`}
                    className={`flex-1 text-sm ${t.status === "done" ? "text-muted line-through" : "font-medium"}`}
                  >
                    {t.title}
                    {t.rescheduled && (
                      <span className="ml-2 text-xs text-muted">
                        (rescheduled)
                      </span>
                    )}
                  </label>
                  <Badge tone={KIND[t.kind][1]}>{KIND[t.kind][0]}</Badge>
                  <span className="w-12 text-right text-xs tabular-nums text-muted">
                    {t.minutes} min
                  </span>
                  {t.status !== "done" && (
                    <button
                      className="text-xs text-forest underline"
                      onClick={async () => {
                        const day = window.prompt(
                          "Move to date (YYYY-MM-DD)",
                          t.day,
                        );
                        if (!day) return;
                        try {
                          await api.patch(`/planner/tasks/${t.id}`, { day });
                          onChange(await api.get(`/planner/plans/${plan.id}`));
                        } catch (e) {
                          setError(e.message);
                        }
                      }}
                    >
                      Move
                    </button>
                  )}
                  {t.status === "pending" && (
                    <button
                      className="text-xs text-muted underline"
                      onClick={async () => {
                        const reason = window.prompt(
                          "Why are you skipping this task?",
                        );
                        if (!reason) return;
                        try {
                          await api.patch(`/planner/tasks/${t.id}`, {
                            status: "skipped",
                            reason,
                          });
                          onChange(await api.get(`/planner/plans/${plan.id}`));
                        } catch (e) {
                          setError(e.message);
                        }
                      }}
                    >
                      Skip
                    </button>
                  )}
                  {t.status === "skipped" && (
                    <span className="text-xs text-muted">
                      Skipped: {t.reason}
                    </span>
                  )}
                  {t.lecture_id && (
                    <Link
                      to={lectureLink(t.lecture_id)}
                      className="text-sm font-semibold text-forest hover:underline"
                    >
                      Open
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function Planner() {
  const [plans, setPlans] = useState([]);
  const [lectures, setLectures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    exam_date: "",
    daily_minutes: 60,
    ids: [],
  });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [p, l] = await Promise.all([
        api.get("/planner/plans"),
        api.get("/lectures"),
      ]);
      setPlans(p.items);
      setLectures(l.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setFormError("");
    if (!form.ids.length)
      return setFormError("Choose at least one lecture to study.");
    setSaving(true);
    try {
      const plan = await api.post("/planner/plans", {
        title: form.title.trim(),
        exam_date: form.exam_date,
        daily_minutes: Number(form.daily_minutes),
        lecture_ids: form.ids,
      });
      setPlans((p) => [plan, ...p]);
      setForm({ title: "", exam_date: "", daily_minutes: 60, ids: [] });
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };
  const replace = (n) =>
    setPlans((ps) => ps.map((p) => (p.id === n.id ? n : p)));
  const remove = async (id) => {
    await api.del(`/planner/plans/${id}`);
    setPlans((ps) => ps.filter((p) => p.id !== id));
  };

  if (loading) return <Loading label="Opening your planner…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  const min = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

  return (
    <div className="space-y-8">
      <header>
        <span className="eyebrow">Plan · Study Planner</span>
        <h1 className="mt-1 font-display text-4xl sm:text-5xl">
          Work backwards from the exam
        </h1>
        <p className="mt-2 max-w-xl text-muted">
          Pick your lectures and an exam date. The planner schedules each
          lecture, then revision at +1, +3 and +7 days, plus extra practice on
          topics where your mastery is low. Missed a day? Reschedule moves it
          for you.
        </p>
      </header>

      {lectures.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={CalendarDays}
            title="Add a lecture first"
            description="Plans are built from the lectures in your library."
            action={
              <Link to="/learn/new" className="btn btn-primary">
                Add a lecture
              </Link>
            }
          />
        </div>
      ) : (
        <form
          onSubmit={create}
          className="card grid gap-4 p-5 sm:grid-cols-3 sm:p-6"
          aria-label="Create a study plan"
        >
          <div className="sm:col-span-3 sm:col-start-1 grid gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="p-title" className="text-sm font-semibold">
                Plan name
              </label>
              <input
                id="p-title"
                required
                maxLength={160}
                className="field mt-1"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Physics midterm"
              />
            </div>
            <div>
              <label htmlFor="p-date" className="text-sm font-semibold">
                Exam date
              </label>
              <input
                id="p-date"
                type="date"
                required
                min={min}
                className="field mt-1"
                value={form.exam_date}
                onChange={(e) =>
                  setForm({ ...form, exam_date: e.target.value })
                }
              />
            </div>
            <div>
              <label htmlFor="p-min" className="text-sm font-semibold">
                Minutes per day
              </label>
              <input
                id="p-min"
                type="number"
                min={15}
                max={480}
                step={5}
                className="field mt-1"
                value={form.daily_minutes}
                onChange={(e) =>
                  setForm({ ...form, daily_minutes: e.target.value })
                }
              />
            </div>
          </div>
          <fieldset className="sm:col-span-3">
            <legend className="text-sm font-semibold">Lectures to cover</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {lectures.map((l) => {
                const on = form.ids.includes(l.id);
                return (
                  <label
                    key={l.id}
                    className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm font-semibold ${on ? "border-forest bg-forest text-white" : "border-line2 text-muted hover:border-ink"}`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={on}
                      onChange={() =>
                        setForm({
                          ...form,
                          ids: on
                            ? form.ids.filter((i) => i !== l.id)
                            : [...form.ids, l.id],
                        })
                      }
                    />
                    {l.title}
                  </label>
                );
              })}
            </div>
          </fieldset>
          <div className="flex flex-wrap items-center gap-3 sm:col-span-3">
            <Button type="submit" loading={saving}>
              Build my plan
            </Button>
            {formError && (
              <p role="alert" className="text-sm font-medium text-danger">
                {formError}
              </p>
            )}
          </div>
        </form>
      )}

      {plans.map((p) => (
        <PlanView
          key={p.id}
          plan={p}
          onChange={replace}
          onDelete={() => remove(p.id)}
        />
      ))}
    </div>
  );
}
