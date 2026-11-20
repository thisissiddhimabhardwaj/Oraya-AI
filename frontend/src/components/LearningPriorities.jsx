import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
export default function LearningPriorities() {
  const [data, setData] = useState(null);
  useEffect(() => {
    let live = true;
    Promise.all([
      api.get("/planner/plans"),
      api.get("/doubts"),
      api.get("/flashcards/stats"),
    ])
      .then(([plans, doubts, cards]) => {
        if (live) setData({ plans: plans.items, doubts: doubts.items, cards });
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  if (!data) return null;
  const d = new Date(),
    today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const tasks = data.plans
    .flatMap((p) => p.tasks)
    .filter((t) => t.status === "pending" && t.day <= today);
  const due = data.doubts.filter(
    (x) => x.status !== "resolved" && x.due_date && x.due_date <= today,
  );
  const exams = data.plans
    .filter((p) => p.exam_date >= today)
    .sort((a, b) => a.exam_date.localeCompare(b.exam_date));
  return (
    <section className="learning-priorities">
      <div>
        <p className="eyebrow">A LITTLE DIRECTION</p>
        <h2>Today, at your pace.</h2>
      </div>
      <div className="priority-columns">
        <article>
          <span>01 / MAKE IT STICK</span>
          <h3>{data.cards.due} cards ready to revisit</h3>
          <p>
            {data.cards.due
              ? "A small review makes room for lasting understanding."
              : "Your next review will appear when it is due."}
          </p>
          <Link to="/revision">Open revision →</Link>
        </article>
        <article>
          <span>02 / YOUR NEXT STEPS</span>
          <h3>
            {tasks.length} study tasks · {due.length} doubts due
          </h3>
          {tasks.slice(0, 3).map((t) => (
            <Link
              key={t.id}
              to={t.lecture_id ? `/lecture/${t.lecture_id}` : "/planner"}
            >
              {t.title} · {t.minutes} min ↗
            </Link>
          ))}
          {!tasks.length && (
            <p>No study tasks due. Build a plan around your next goal.</p>
          )}
          <Link to="/planner">
            {due.length ? "Review your study plan" : "Open study planner"} →
          </Link>
        </article>
        <article>
          <span>03 / ON THE HORIZON</span>
          <h3>{exams.length ? "Your next exam" : "Room for a new goal."}</h3>
          {exams.slice(0, 2).map((p) => (
            <p key={p.id}>
              {p.title}
              <br />
              <strong>
                {new Date(`${p.exam_date}T12:00:00`).toLocaleDateString(
                  undefined,
                  { day: "numeric", month: "long" },
                )}
              </strong>
            </p>
          ))}
          {!exams.length && (
            <p>Add an exam date to your study plan when you are ready.</p>
          )}
          <Link to="/planner">Shape your week →</Link>
        </article>
      </div>
    </section>
  );
}
