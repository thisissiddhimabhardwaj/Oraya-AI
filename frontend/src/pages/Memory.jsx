import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button, ErrorState } from "../components/ui";
export default function Memory() {
  const { user, updateProfile } = useAuth();
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [goal, setGoal] = useState(""),
    [recordKind, setRecordKind] = useState("goal"),
    [prefs, setPrefs] = useState({}),
    [name, setName] = useState(user?.name || ""),
    [notice, setNotice] = useState("");
  const load = () =>
    api
      .get("/memory")
      .then((d) => {
        setData(d);
        setPrefs(d.preferences || {});
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  const run = async (fn) => {
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <div className="studio-page">
      <header className="studio-heading">
        <p className="eyebrow">YOUR LEARNING · ON YOUR TERMS</p>
        <h1>A little more you.</h1>
        <p>
          Inspect your learning evidence, set a direction, and choose what to
          keep.
        </p>
      </header>
      {error && <ErrorState message={error} />}
      <div className="studio-split">
        <form
          className="studio-paper"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await updateProfile({ name, prefs });
              setNotice("Preferences saved.");
            });
          }}
        >
          <h2>Your direction</h2>
          <label className="studio-label">
            Name
            <input
              className="field"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="studio-label">
            Academic goal
            <input
              className="field"
              value={prefs.goals || ""}
              onChange={(e) => setPrefs({ ...prefs, goals: e.target.value })}
            />
          </label>
          <label className="studio-label">
            Exam date (optional)
            <input
              className="field"
              type="date"
              value={prefs.exam_date || ""}
              onChange={(e) =>
                setPrefs({ ...prefs, exam_date: e.target.value })
              }
            />
          </label>
          <label className="studio-label">
            Daily study minutes
            <input
              className="field"
              type="number"
              min="5"
              max="480"
              value={prefs.daily_minutes || 30}
              onChange={(e) =>
                setPrefs({ ...prefs, daily_minutes: Number(e.target.value) })
              }
            />
          </label>
          <label className="studio-label">
            Current priorities
            <textarea
              className="field"
              value={prefs.priorities || ""}
              onChange={(e) =>
                setPrefs({ ...prefs, priorities: e.target.value })
              }
            />
          </label>
          <Button type="submit">Save preferences</Button>
          {notice && <p role="status">{notice}</p>}
        </form>
        <aside className="studio-aside">
          <span className="studio-big-symbol">✦</span>
          <h2>Your evidence, explained.</h2>
          <p>{data?.method}</p>
          <dl className="studio-evidence">
            <div>
              <dt>Saved quiz attempts</dt>
              <dd>{data?.evidence.quiz_attempts ?? "—"}</dd>
            </div>
            <div>
              <dt>Card reviews</dt>
              <dd>{data?.evidence.reviews ?? "—"}</dd>
            </div>
          </dl>
          {data?.evidence.topics.map((t) => (
            <div className="studio-history" key={t.topic}>
              <span>{t.topic}</span>
              <b>{Math.round(t.mastery * 100)}%</b>
              <button
                className="text-xs text-forest underline"
                onClick={() => {
                  if (
                    window.confirm(
                      "Forget this topic score? Future quizzes can rebuild it.",
                    )
                  )
                    run(() => api.del(`/memory/evidence/mastery/${t.id}`));
                }}
              >
                Forget score
              </button>
            </div>
          ))}
        </aside>
      </div>
      <section className="studio-paper mt-6">
        <h2>Keep what matters.</h2>
        <form
          className="studio-inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await api.post("/memory", {
                title: goal,
                kind: recordKind,
                data: {},
              });
              setGoal("");
            });
          }}
        >
          <label className="sr-only" htmlFor="goal">
            Learning goal or correction
          </label>
          <label className="sr-only" htmlFor="record-kind">
            Record type
          </label>
          <select
            id="record-kind"
            className="field !w-auto"
            value={recordKind}
            onChange={(e) => setRecordKind(e.target.value)}
          >
            <option value="goal">Learning goal</option>
            <option value="correction">Correction / priority</option>
          </select>
          <input
            id="goal"
            className="field"
            required
            maxLength={200}
            placeholder="A learning goal or a correction to remember…"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <Button type="submit">Save</Button>
        </form>
        {data?.records
          .filter(
            (r) => !["material_metadata", "library_chat"].includes(r.kind),
          )
          .map((r) => (
            <div className="studio-history" key={r.id}>
              <div>
                <small>{r.kind}</small>
                <p>{r.title}</p>
                {r.data?.content && (
                  <p className="whitespace-pre-wrap">{r.data.content}</p>
                )}
              </div>
              <Button
                variant="secondary"
                onClick={() => run(() => api.del(`/memory/${r.id}`))}
              >
                Delete
              </Button>
            </div>
          ))}
      </section>
      <section className="studio-paper mt-6">
        <h2>Your learning trail.</h2>
        <details>
          <summary className="cursor-pointer text-sm text-forest">
            Quiz attempts & incorrect answers
          </summary>
          {data?.evidence.quiz_history?.map((a) => (
            <article className="memory-evidence-row" key={a.id}>
              <h3>
                Quiz #{a.quiz_id} · {Math.round(a.score * 100)}%
              </h3>
              <small>{new Date(a.created_at).toLocaleString()}</small>
              {a.results
                .filter((r) => !r.correct)
                .map((r, i) => (
                  <p key={i}>
                    {r.topic}: {r.correct_answer} — {r.explanation}
                  </p>
                ))}
            </article>
          ))}
        </details>
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-forest">
            Card review history
          </summary>
          {data?.evidence.review_history?.map((r) => (
            <p className="memory-evidence-row" key={r.id}>
              Card #{r.flashcard_id} ·{" "}
              {["Again", "Hard", "Good", "Easy"][r.quality]} · next interval{" "}
              {r.next_interval_days} days
              <br />
              <small>{new Date(r.created_at).toLocaleString()}</small>
            </p>
          ))}
        </details>
      </section>
      <section className="studio-privacy">
        <h2>Start fresh.</h2>
        <p>
          Reset learning memory, quiz and exam history, review logs, topic
          scores, playback history, and preferences. Source lectures,
          flashcards, notes, study plans, and room contributions remain. Review
          schedules on existing cards are retained.
        </p>
        <Button
          variant="secondary"
          onClick={() => {
            if (
              window.confirm(
                "Permanently clear the learning data listed above? This cannot be undone.",
              )
            )
              run(() => api.del("/memory"));
          }}
        >
          Clear learning memory
        </Button>
      </section>
    </div>
  );
}
