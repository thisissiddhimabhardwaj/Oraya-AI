import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Clock, Flag, ArrowRight, CheckCircle } from "lucide-react";
import { api } from "../lib/api";
import { Button, ErrorState } from "../components/ui";

export default function Exams() {
  const [lectures, setLectures] = useState([]),
    [history, setHistory] = useState([]),
    [exam, setExam] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [index, setIndex] = useState(0),
    [remaining, setRemaining] = useState(0),
    [form, setForm] = useState({
      lecture_ids: [],
      count: 5,
      minutes: 15,
      difficulty: "all",
      title: "My practice exam",
    });
  const offset = useRef(0),
    latest = useRef(null);
  latest.current = exam;
  const load = () =>
    Promise.all([api.get("/lectures"), api.get("/exams")])
      .then(([l, e]) => {
        setLectures(l.items);
        setHistory(e.items);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  const adopt = (e) => {
    offset.current = Date.parse(e.server_now) - Date.now();
    setExam(e);
  };
  const submit = async () => {
    const current = latest.current;
    if (!current || current.submitted_at) return;
    setBusy(true);
    try {
      adopt(await api.post(`/exams/${current.id}/submit`, {}));
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (!exam || exam.submitted_at) return;
    const tick = () => {
      const left = Math.max(
        0,
        Math.ceil(
          (Date.parse(exam.deadline) - Date.now() - offset.current) / 1000,
        ),
      );
      setRemaining(left);
      if (left === 0) submit();
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [exam?.id, exam?.submitted_at]);
  const save = async (answers, marked) => {
    setBusy(true);
    setError("");
    try {
      adopt(await api.patch(`/exams/${exam.id}`, { answers, marked }));
    } catch (e) {
      setError(e.message);
      try {
        adopt(await api.get(`/exams/${exam.id}`));
      } catch {}
    } finally {
      setBusy(false);
    }
  };
  const start = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      adopt(await api.post("/exams", form));
      setIndex(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const q = exam?.questions[index];
  return (
    <div className="studio-page">
      <header className="studio-heading">
        <p className="eyebrow">PRACTISE · A LITTLE CLOSER TO MASTERY</p>
        <h1>Make room for your best.</h1>
        <p>
          Focus, practise, and find out what to revisit. Your answers and time
          are saved on the server.
        </p>
      </header>
      {error && <ErrorState message={error} />}
      {!exam ? (
        <div className="studio-split">
          <form className="studio-paper" onSubmit={start}>
            <h2>Your next challenge</h2>
            <label className="studio-label">
              Exam title
              <input
                className="field"
                value={form.title}
                required
                maxLength={160}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <fieldset className="studio-fieldset">
              <legend>Choose your materials</legend>
              {lectures.length === 0 ? (
                <p>
                  Add a lecture and generate a quiz to build your question bank.{" "}
                  <Link to="/learn/new" className="text-forest underline">
                    Add material
                  </Link>
                </p>
              ) : (
                lectures.map((l) => (
                  <label key={l.id} className="studio-check">
                    <input
                      type="checkbox"
                      checked={form.lecture_ids.includes(l.id)}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          lecture_ids: e.target.checked
                            ? [...form.lecture_ids, l.id]
                            : form.lecture_ids.filter((x) => x !== l.id),
                        })
                      }
                    />
                    {l.title}
                  </label>
                ))
              )}
            </fieldset>
            <div className="studio-form-row">
              <label>
                Questions
                <input
                  className="field"
                  type="number"
                  min="1"
                  max="50"
                  value={form.count}
                  onChange={(e) =>
                    setForm({ ...form, count: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                Minutes
                <input
                  className="field"
                  type="number"
                  min="1"
                  max="180"
                  value={form.minutes}
                  onChange={(e) =>
                    setForm({ ...form, minutes: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                Difficulty
                <select
                  className="field"
                  value={form.difficulty}
                  onChange={(e) =>
                    setForm({ ...form, difficulty: e.target.value })
                  }
                >
                  {["all", "easy", "medium", "hard"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
            </div>
            <p className="studio-notice">
              Exams use saved multiple-choice questions. Generate quizzes in
              your lecture workspace first. Once started, the timer continues
              when you leave. Unanswered questions score zero.
            </p>
            <Button type="submit" disabled={busy || !form.lecture_ids.length}>
              Start exam <ArrowRight size={16} />
            </Button>
          </form>
          <aside className="studio-aside">
            <span className="studio-big-symbol">✧</span>
            <h2>Progress, one question at a time.</h2>
            <p>A score is a starting point for your next study session.</p>
            <h3>Previous attempts</h3>
            {history.length === 0 ? (
              <p>No exams yet. Your first one starts here.</p>
            ) : (
              history.map((e) => (
                <button
                  className="studio-history"
                  key={e.id}
                  onClick={() => {
                    adopt(e);
                    setIndex(0);
                  }}
                >
                  <span>{e.title}</span>
                  <b>
                    {e.submitted_at
                      ? `${Math.round(e.score * 100)}%`
                      : "Resume →"}
                  </b>
                </button>
              ))
            )}
          </aside>
        </div>
      ) : exam.submitted_at ? (
        <section className="studio-paper">
          <p className="eyebrow">EXAM COMPLETE</p>
          <h2 className="studio-score">
            {Math.round(exam.score * 100)}
            <small>%</small>
          </h2>
          <p>
            {exam.results.filter((r) => r.correct).length} of{" "}
            {exam.results.length} correct. Review your reasoning below.
          </p>
          <div className="studio-results">
            {exam.results.map((r, i) => (
              <article key={r.question_id}>
                <span className={r.correct ? "text-forest" : "text-danger"}>
                  {r.correct ? "✓ Correct" : "↗ Revisit"} · Question {i + 1}
                </span>
                <h3>{r.prompt}</h3>
                <p>Your answer: {r.answer || "Not answered"}</p>
                <p>
                  Correct answer: <b>{r.correct_answer}</b>
                </p>
                <p>{r.explanation}</p>
                <small>{r.topic}</small>
              </article>
            ))}
          </div>
          <Button
            onClick={() => {
              setExam(null);
              setIndex(0);
            }}
          >
            Build another exam
          </Button>
        </section>
      ) : (
        <div className="studio-exam">
          <aside className="exam-map">
            <p className="exam-clock" role="timer">
              <Clock size={18} />
              {Math.floor(remaining / 60)}:
              {String(remaining % 60).padStart(2, "0")}
            </p>
            <h2>{exam.title}</h2>
            <div className="question-map">
              {exam.questions.map((q, i) => (
                <button
                  key={q.id}
                  aria-label={`Question ${i + 1}${exam.marked.includes(q.id) ? ", marked for review" : ""}`}
                  aria-current={index === i ? "step" : undefined}
                  className={`${exam.answers[q.id] ? "answered" : ""} ${index === i ? "current" : ""}`}
                  onClick={() => setIndex(i)}
                >
                  {i + 1}
                  {exam.marked.includes(q.id) && " ⚑"}
                </button>
              ))}
            </div>
            <p className="studio-notice">
              Answers save after each choice. Mark questions to revisit before
              submitting.
            </p>
            <Button
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    "Submit this exam? You cannot change answers afterwards.",
                  )
                )
                  submit();
              }}
            >
              Submit exam
            </Button>
          </aside>
          <section className="studio-paper">
            <p className="eyebrow">
              QUESTION {index + 1} OF {exam.questions.length}
            </p>
            <h2>{q?.prompt}</h2>
            <div className="exam-options">
              {q?.options?.map((o) => (
                <label key={o}>
                  <input
                    name="answer"
                    type="radio"
                    checked={exam.answers[q.id] === o}
                    disabled={busy}
                    onChange={() =>
                      save({ ...exam.answers, [q.id]: o }, exam.marked)
                    }
                  />
                  {o}
                </label>
              ))}
            </div>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                save(
                  exam.answers,
                  exam.marked.includes(q.id)
                    ? exam.marked.filter((x) => x !== q.id)
                    : [...exam.marked, q.id],
                )
              }
            >
              <Flag size={15} />
              {exam.marked.includes(q.id) ? "Unmark" : "Mark for review"}
            </Button>
            <div className="studio-bottom">
              <Button
                variant="secondary"
                disabled={index === 0}
                onClick={() => setIndex((i) => i - 1)}
              >
                Previous
              </Button>
              <span role="status">
                {busy
                  ? "Saving…"
                  : error
                    ? "The last change could not be saved"
                    : "All changes saved"}
              </span>
              <Button
                disabled={index >= exam.questions.length - 1}
                onClick={() => setIndex((i) => i + 1)}
              >
                Next <ArrowRight size={16} />
              </Button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
