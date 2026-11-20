import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button, ErrorState, Loading } from "../components/ui";
const rating = ["Again", "Hard", "Good", "Easy"];
export default function Revision() {
  const [data, setData] = useState(null),
    [session, setSession] = useState(null),
    [answer, setAnswer] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [filter, setFilter] = useState("due");
  const load = async () => {
    const [d, s] = await Promise.all([
      api.get("/revision/overview"),
      api.get("/revision/sessions/active"),
    ]);
    setData(d);
    setSession(s);
    setAnswer(s?.current?.answer || "");
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  const run = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  if (!data && !error) return <Loading label="Finding your next review…" />;
  const current = session?.current;
  return (
    <div className="revision-studio">
      <header className="studio-heading">
        <p className="eyebrow">SMART REVISION / UNDERSTANDING THAT STAYS</p>
        <h1>A little recall. A lasting difference.</h1>
        <p>
          Your real learning queue, scheduled with SM-2. Answer first, compare
          with your source, then rate what you remembered.
        </p>
      </header>
      {error && <ErrorState message={error} onRetry={() => run(load)} />}
      {data?.total === 0 ? (
        <section className="revision-empty">
          <span>✧</span>
          <h2>Give your next review a beginning.</h2>
          <p>
            Add a lecture or document, then create flashcards from its source
            text or your notes. They will appear here when due.
          </p>
          <Link className="btn btn-primary" to="/flashcards">
            Create revision material →
          </Link>
          <Link to="/library">Open your learning library ↗</Link>
        </section>
      ) : (
        <>
          <div className="revision-summary">
            {[
              ["Due now", data?.due.length],
              ["Overdue", data?.overdue],
              ["Weak concepts", data?.weak.length],
              ["Mastered", data?.mastered.length],
            ].map(([t, n]) => (
              <div key={t}>
                <b>{n}</b>
                <span>{t}</span>
              </div>
            ))}
          </div>
          {session?.status === "active" && current ? (
            <section className="recall-session">
              <div className="recall-session-meta">
                <span>YOUR SAVED SESSION</span>
                <span>
                  {session.cursor + 1} / {session.total}
                </span>
              </div>
              <p className="eyebrow">{current.topic || "SOURCE RECALL"}</p>
              <h2>{current.front}</h2>
              {current.back === null ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(async () =>
                      setSession(
                        await api.post(
                          `/revision/sessions/${session.id}/reveal`,
                          { card_id: current.id, answer },
                        ),
                      ),
                    );
                  }}
                >
                  <label className="studio-label">
                    What do you remember?
                    <textarea
                      className="field"
                      rows={4}
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      placeholder="Write your answer before looking at the source…"
                      required
                      maxLength={4000}
                    />
                  </label>
                  <Button type="submit" disabled={busy || !answer.trim()}>
                    Compare with the source
                  </Button>
                </form>
              ) : (
                <>
                  <div className="recall-comparison">
                    <article>
                      <span>YOUR ANSWER</span>
                      <p>{current.answer}</p>
                    </article>
                    <article>
                      <span>FROM YOUR LEARNING MATERIAL</span>
                      <p>{current.back}</p>
                      <Link to={`/lecture/${current.lecture_id}`}>
                        Revisit source ↗
                      </Link>
                    </article>
                  </div>
                  <p className="text-sm my-5">
                    How well did you recall this? Your self-assessment sets the
                    next review date.
                  </p>
                  <div className="recall-ratings">
                    {rating.map((r, q) => (
                      <Button
                        key={r}
                        variant={q > 1 ? "primary" : "secondary"}
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            const next = await api.post(
                              `/revision/sessions/${session.id}/rate`,
                              { card_id: current.id, quality: q },
                            );
                            setSession(next);
                            setAnswer(next.current?.answer || "");
                            setData(await api.get("/revision/overview"));
                          })
                        }
                      >
                        {r}
                      </Button>
                    ))}
                  </div>
                </>
              )}
              {session.responses.length > 0 && (
                <p className="revision-next-date" role="status">
                  Last concept scheduled for{" "}
                  {new Date(session.responses.at(-1).next_due).toLocaleString()}
                  .
                </p>
              )}
              <p className="studio-notice">
                Your answer, session position and schedule save on the server.
                You can leave and resume after logging in.
              </p>
            </section>
          ) : (
            <section className="revision-start">
              <h2>
                {session?.status === "completed"
                  ? "A good session. A stronger memory."
                  : data?.due.length
                    ? "Your next review is ready."
                    : "You are up to date."}
              </h2>
              <p>
                {session?.status === "completed"
                  ? `${session.responses.length} ${session.responses.length === 1 ? "concept" : "concepts"} reviewed. Your new dates are saved.`
                  : data?.due.length
                    ? "Start with the concepts that need your attention most."
                    : "Your next scheduled concepts are listed below. There is no empty session to start."}
              </p>
              {data?.due.length > 0 && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      setSession(
                        await api.post("/revision/sessions", { limit: 20 }),
                      );
                      setAnswer("");
                    })
                  }
                >
                  Review {Math.min(20, data.due.length)} due{" "}
                  {data.due.length === 1 ? "concept" : "concepts"} →
                </Button>
              )}
              {session?.responses.map((r) => (
                <p className="revision-next-date" key={r.card_id}>
                  Card #{r.card_id} · {rating[r.quality]} · next review{" "}
                  {new Date(r.next_due).toLocaleString()}
                </p>
              ))}
            </section>
          )}
          <div className="revision-lower">
            <section>
              <div className="revision-filters" aria-label="Revision concepts">
                {["due", "upcoming", "weak", "mastered"].map((f) => (
                  <button
                    key={f}
                    aria-pressed={filter === f}
                    onClick={() => setFilter(f)}
                  >
                    {f}
                  </button>
                ))}
              </div>
              {data?.[filter]?.length === 0 ? (
                <p className="studio-notice">
                  No concepts in this category yet.
                </p>
              ) : (
                data?.[filter]?.map((c) => (
                  <article className="revision-concept" key={c.id}>
                    <div>
                      <small>
                        {c.topic || "General"} · {c.stage}
                      </small>
                      <h3>{c.front}</h3>
                      <p>
                        {c.reviews} reviews ·{" "}
                        {new Date(c.due_at).toLocaleString()}
                      </p>
                      {c.last_reviewed && (
                        <p>
                          Last reviewed{" "}
                          {new Date(c.last_reviewed).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <Link to={`/lecture/${c.lecture_id}`}>Source ↗</Link>
                  </article>
                ))
              )}
            </section>
            <aside>
              <h2>Your revision calendar</h2>
              {data?.calendar.map((d) => (
                <div className="revision-calendar-day" key={d.date}>
                  <time>
                    {new Date(`${d.date}T12:00:00`).toLocaleDateString(
                      undefined,
                      { weekday: "short", month: "short", day: "numeric" },
                    )}
                  </time>
                  <b>
                    {d.cards} {d.cards === 1 ? "concept" : "concepts"}
                  </b>
                </div>
              ))}
              <h2 className="mt-8">Performance history</h2>
              {data?.history.length === 0 ? (
                <p className="studio-notice">
                  Completed reviews will appear here.
                </p>
              ) : (
                data?.history.slice(0, 15).map((h) => (
                  <p className="revision-history" key={h.id}>
                    {rating[h.quality]} · Card #{h.card_id}
                    <small>
                      {new Date(h.created_at).toLocaleString()} · next interval{" "}
                      {h.next_interval} {h.next_interval === 1 ? "day" : "days"}
                    </small>
                  </p>
                ))
              )}
            </aside>
          </div>
          <p className="studio-notice">{data?.method}</p>
        </>
      )}
    </div>
  );
}
