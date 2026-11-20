import { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui";
export default function PassageTools({
  lecture,
  selection = "",
  timestamp = 0,
}) {
  const [title, setTitle] = useState(""),
    [content, setContent] = useState(""),
    [mode, setMode] = useState("note"),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="passage-tools">
      <details>
        <summary>
          Make this idea yours <span>Notes & flashcards ＋</span>
        </summary>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setNotice("");
            try {
              if (mode === "note")
                await api.post(`/lectures/${lecture.id}/notes/manual`, {
                  title,
                  content: content || selection,
                  timestamp: lecture.source === "document" ? null : timestamp,
                });
              else
                await api.post("/cards", {
                  lecture_id: lecture.id,
                  front: title,
                  back: content || selection,
                  topic: "My deck",
                });
              window.dispatchEvent(new CustomEvent("oraya:notes-changed"));
              setTitle("");
              setContent("");
              setNotice(
                mode === "note"
                  ? "Note saved. Find it in Notes."
                  : "Flashcard saved. Find it in Flashcards.",
              );
            } catch (e) {
              setNotice(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Save as
            <select
              className="field"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="note">A personal note</option>
              <option value="card">A flashcard</option>
            </select>
          </label>
          <label>
            {mode === "note" ? "Note title" : "Question"}
            <input
              className="field"
              required
              maxLength={500}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            {mode === "note" ? "Your note" : "Answer"}
            <textarea
              className="field"
              required
              value={content || selection}
              onChange={(e) => setContent(e.target.value)}
              rows={3}
              maxLength={6000}
            />
          </label>
          {selection && (
            <p>
              Selected source passage is ready to save. You can edit it above.
            </p>
          )}
          <Button disabled={busy} type="submit">
            {busy
              ? "Saving…"
              : mode === "note"
                ? "Save note"
                : "Create flashcard"}
          </Button>
          {notice && <p role="status">{notice}</p>}
        </form>
      </details>
    </section>
  );
}
