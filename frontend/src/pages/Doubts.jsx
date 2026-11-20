import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, HelpCircle, Layers, Play, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Loading,
} from "../components/ui";
import { api } from "../lib/api";
import { fmtTs, lectureLink, parseTs } from "../lib/format";

const STATUS = {
  unresolved: { label: "Unresolved", tone: "coral" },
  in_progress: { label: "In progress", tone: "warn" },
  resolved: { label: "Resolved", tone: "ok" },
};

function DoubtCard({ d, onChange, onDelete }) {
  const [note, setNote] = useState(d.note);
  const [question, setQuestion] = useState(d.question);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const dirty = note !== d.note;

  const run = async (fn, ok) => {
    setBusy(true);
    setMsg("");
    try {
      await fn();
      if (ok) setMsg(ok);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };
  const patch = (body) =>
    run(async () => onChange(await api.patch(`/doubts/${d.id}`, body)));

  return (
    <li className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl font-display text-xl leading-snug">
          {d.question}
        </p>
        <Badge tone={STATUS[d.status].tone}>{STATUS[d.status].label}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
        {d.subject && <span>{d.subject}</span>}
        {d.lecture_id && (
          <Link
            className="inline-flex items-center gap-1 font-semibold text-forest underline-offset-2 hover:underline"
            to={lectureLink(d.lecture_id, d.timestamp)}
          >
            <Play className="h-3.5 w-3.5" aria-hidden="true" />
            {d.lecture_title || "Lecture"}
            {d.timestamp != null && ` · ${fmtTs(d.timestamp)}`}
          </Link>
        )}
      </div>

      <details className="mt-4 text-sm">
        <summary className="cursor-pointer text-forest">
          Edit question, priority & revisit date
        </summary>
        <label className="studio-label">
          Question
          <input
            className="field"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={2000}
          />
        </label>
        <Button
          variant="secondary"
          disabled={busy || question.trim().length < 3}
          onClick={() => patch({ question })}
        >
          Save question
        </Button>
        <label className="studio-label">
          Priority
          <select
            className="field"
            value={d.priority || "normal"}
            onChange={(e) => patch({ priority: e.target.value })}
          >
            {["low", "normal", "high"].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="studio-label">
          Revisit date
          <input
            type="date"
            className="field"
            value={d.due_date || ""}
            onChange={(e) => patch({ due_date: e.target.value || null })}
          />
        </label>
        <p className="studio-notice">
          Due dates are shown in-app. No email or push reminders are sent.
        </p>
        {d.history?.map((h, i) => (
          <p className="text-xs text-muted my-2" key={i}>
            {h.from} → {h.to} · {new Date(h.at).toLocaleString()}
          </p>
        ))}
      </details>
      {d.due_date && (
        <p className="mt-3 text-xs text-forest">
          Revisit {d.due_date} · {d.priority} priority
        </p>
      )}
      <label
        className="mt-4 block text-sm font-semibold"
        htmlFor={`note-${d.id}`}
      >
        Your notes / resolution
      </label>
      <textarea
        id={`note-${d.id}`}
        className="field mt-1 min-h-20 py-2"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Write what you worked out. This becomes the flashcard answer."
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {dirty && (
          <Button
            size="sm"
            variant="secondary"
            loading={busy}
            onClick={() => patch({ note })}
          >
            Save notes
          </Button>
        )}
        {d.status !== "in_progress" && d.status !== "resolved" && (
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => patch({ status: "in_progress" })}
          >
            Start working on it
          </Button>
        )}
        {d.status !== "resolved" ? (
          <Button
            disabled={busy}
            onClick={() => patch({ status: "resolved", note })}
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            Mark resolved
          </Button>
        ) : (
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => patch({ status: "unresolved" })}
          >
            Reopen
          </Button>
        )}
        {d.status === "resolved" && !d.flashcard_id && (
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await api.post(`/doubts/${d.id}/flashcard`);
                onChange({ ...d, flashcard_id: -1 });
              }, "Flashcard created.")
            }
          >
            <Layers className="h-4 w-4" aria-hidden="true" />
            Make flashcard
          </Button>
        )}
        {d.flashcard_id && <Badge tone="sage">Flashcard created</Badge>}
        <Button
          variant="ghost"
          className="ml-auto text-danger"
          disabled={busy}
          aria-label={`Delete doubt: ${d.question}`}
          onClick={() =>
            run(async () => {
              await api.del(`/doubts/${d.id}`);
              onDelete(d.id);
            })
          }
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
      {msg && (
        <p role="status" className="mt-2 text-sm text-muted">
          {msg}
        </p>
      )}
    </li>
  );
}

export default function Doubts() {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [lectures, setLectures] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    question: "",
    subject: "",
    lecture_id: "",
    ts: "",
  });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [d, l] = await Promise.all([
        api.get(`/doubts${filter ? `?status=${filter}` : ""}`),
        api.get("/lectures"),
      ]);
      setItems(
        d.items.slice().sort((a, b) => {
          const aOpen = a.status !== "resolved",
            bOpen = b.status !== "resolved";
          if (aOpen !== bOpen) return aOpen ? -1 : 1;
          const dates = (a.due_date || "9999").localeCompare(
            b.due_date || "9999",
          );
          return (
            dates ||
            { high: 0, normal: 1, low: 2 }[a.priority || "normal"] -
              { high: 0, normal: 1, low: 2 }[b.priority || "normal"]
          );
        }),
      );
      setCounts(d.counts);
      setLectures(l.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);
  useEffect(() => {
    load();
  }, [load]);

  const add = async (e) => {
    e.preventDefault();
    setFormError("");
    const ts = parseTs(form.ts);
    if (Number.isNaN(ts))
      return setFormError("Enter the timestamp like 1:35 or 95.");
    if (ts != null && !form.lecture_id)
      return setFormError("Choose a lecture to pin the timestamp to.");
    setSaving(true);
    try {
      await api.post("/doubts", {
        question: form.question.trim(),
        subject: form.subject.trim(),
        lecture_id: form.lecture_id ? Number(form.lecture_id) : null,
        timestamp: ts,
      });
      setForm({
        question: "",
        subject: "",
        lecture_id: form.lecture_id,
        ts: "",
      });
      await load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const replace = (n) =>
    setItems((xs) => xs.map((x) => (x.id === n.id ? { ...x, ...n } : x)));

  if (loading) return <Loading label="Opening your doubts…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-8">
      <header>
        <span className="eyebrow">Practise · Doubt Tracker</span>
        <h1 className="mt-1 font-display text-4xl sm:text-5xl">
          Questions worth keeping
        </h1>
        <p className="mt-2 max-w-xl text-muted">
          Park a question when it comes up, pin it to the moment in the lecture,
          and come back when you can answer it.
        </p>
      </header>

      <form
        onSubmit={add}
        className="card grid gap-4 p-5 sm:grid-cols-6 sm:p-6"
        aria-label="Save a doubt"
      >
        <div className="sm:col-span-6">
          <label htmlFor="d-q" className="text-sm font-semibold">
            What are you unsure about?
          </label>
          <textarea
            id="d-q"
            required
            minLength={3}
            maxLength={2000}
            className="field mt-1 min-h-20 py-2"
            value={form.question}
            onChange={(e) => setForm({ ...form, question: e.target.value })}
            placeholder="e.g. Why do we use net force and not each force separately?"
          />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="d-s" className="text-sm font-semibold">
            Subject <span className="font-normal text-muted">(optional)</span>
          </label>
          <input
            id="d-s"
            className="field mt-1"
            maxLength={120}
            value={form.subject}
            onChange={(e) => setForm({ ...form, subject: e.target.value })}
          />
        </div>
        <div className="sm:col-span-3">
          <label htmlFor="d-l" className="text-sm font-semibold">
            Lecture <span className="font-normal text-muted">(optional)</span>
          </label>
          <select
            id="d-l"
            className="field mt-1"
            value={form.lecture_id}
            onChange={(e) => setForm({ ...form, lecture_id: e.target.value })}
          >
            <option value="">No lecture</option>
            {lectures.map((l) => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-1">
          <label htmlFor="d-t" className="text-sm font-semibold">
            At
          </label>
          <input
            id="d-t"
            className="field mt-1"
            placeholder="1:35"
            inputMode="numeric"
            value={form.ts}
            onChange={(e) => setForm({ ...form, ts: e.target.value })}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-6">
          <Button type="submit" loading={saving}>
            Save doubt
          </Button>
          {formError && (
            <p role="alert" className="text-sm font-medium text-danger">
              {formError}
            </p>
          )}
        </div>
      </form>

      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Filter by status"
      >
        {[
          ["", "All"],
          ...Object.entries(STATUS).map(([k, v]) => [k, v.label]),
        ].map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={filter === k}
            onClick={() => setFilter(k)}
            className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${filter === k ? "border-forest bg-forest text-white" : "border-line2 text-muted hover:border-ink"}`}
          >
            {label}
            {k && counts[k] != null ? ` · ${counts[k]}` : ""}
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={HelpCircle}
            title={
              filter ? "No doubts with this status" : "No doubts saved yet"
            }
            description="When something doesn't click, write it down here instead of losing your place."
          />
        </div>
      ) : (
        <ul className="space-y-4">
          {items.map((d) => (
            <DoubtCard
              key={d.id}
              d={d}
              onChange={replace}
              onDelete={(id) => setItems((xs) => xs.filter((x) => x.id !== id))}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
