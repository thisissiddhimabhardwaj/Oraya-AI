import { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui";
export default function CardManager({ cards, lectures, onChange }) {
  const [editing, setEditing] = useState(null),
    [front, setFront] = useState(""),
    [back, setBack] = useState(""),
    [topic, setTopic] = useState("My deck"),
    [lid, setLid] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [filter, setFilter] = useState("");
  const decks = [...new Set(cards.map((c) => c.topic || "General"))];
  const reset = () => {
    setEditing(null);
    setFront("");
    setBack("");
    setTopic("My deck");
  };
  return (
    <details className="card-manager">
      <summary>
        Your cards, your way <span>Create · Edit · Organise</span>
      </summary>
      <div className="card-manager-grid">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              if (editing)
                await api.patch(`/cards/${editing}`, { front, back, topic });
              else
                await api.post("/cards", {
                  lecture_id: Number(lid || lectures[0]?.id),
                  front,
                  back,
                  topic,
                });
              await onChange();
              reset();
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <h2>{editing ? "Refine this card." : "Write your own."}</h2>
          <label>
            Source material
            <select
              className="field"
              value={lid || lectures[0]?.id || ""}
              disabled={!!editing}
              onChange={(e) => setLid(e.target.value)}
            >
              {lectures.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Deck / topic
            <input
              className="field"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              maxLength={120}
            />
          </label>
          <label>
            Question
            <input
              className="field"
              value={front}
              onChange={(e) => setFront(e.target.value)}
              required
              maxLength={2000}
            />
          </label>
          <label>
            Answer
            <textarea
              className="field"
              value={back}
              onChange={(e) => setBack(e.target.value)}
              required
              maxLength={6000}
              rows={3}
            />
          </label>
          <div className="flex gap-3">
            <Button disabled={busy || lectures.length === 0} type="submit">
              {editing ? "Save changes" : "Create card"}
            </Button>
            {editing && (
              <Button variant="secondary" onClick={reset}>
                Cancel edit
              </Button>
            )}
          </div>
          {error && (
            <p role="alert" className="text-danger">
              {error}
            </p>
          )}
        </form>
        <div>
          <label>
            Browse deck
            <select
              className="field"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="">All decks</option>
              {decks.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <div className="card-manager-list">
            {cards
              .filter((c) => !filter || c.topic === filter)
              .map((c) => (
                <article key={c.id}>
                  <small>{c.topic || "General"}</small>
                  <h3>{c.front}</h3>
                  <p>{c.back}</p>
                  <div>
                    <button
                      onClick={() => {
                        setEditing(c.id);
                        setFront(c.front);
                        setBack(c.back);
                        setTopic(c.topic);
                        setLid(String(c.lecture_id));
                      }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={async () => {
                        if (
                          !window.confirm(
                            "Permanently delete this flashcard and its review history?",
                          )
                        )
                          return;
                        try {
                          await api.del(`/cards/${c.id}`);
                          await onChange();
                        } catch (e) {
                          setError(e.message);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}
          </div>
        </div>
      </div>
    </details>
  );
}
