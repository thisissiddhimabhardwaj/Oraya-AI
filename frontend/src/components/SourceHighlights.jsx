import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
export function HighlightedText({ text, highlights = [] }) {
  const ranges = [];
  for (const h of highlights) {
    const quote = h.data?.content;
    if (!quote) continue;
    let start = text.indexOf(quote);
    while (start >= 0) {
      ranges.push([start, start + quote.length]);
      start = text.indexOf(quote, start + quote.length);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const r of ranges) {
    const prev = merged.at(-1);
    if (prev && r[0] <= prev[1]) prev[1] = Math.max(prev[1], r[1]);
    else merged.push([...r]);
  }
  if (!merged.length) return text;
  const out = [];
  let offset = 0;
  for (const [start, end] of merged) {
    out.push(text.slice(offset, start));
    out.push(
      <mark key={start} className="source-highlight">
        {text.slice(start, end)}
      </mark>,
    );
    offset = end;
  }
  out.push(text.slice(offset));
  return out;
}
export default function SourceHighlights({ lecture, selection, onChange }) {
  const [highlights, setHighlights] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = useCallback(
    () =>
      api
        .get("/memory")
        .then((r) => {
          const items = r.records.filter(
            (x) => x.kind === "highlight" && x.data.lecture_id === lecture.id,
          );
          setHighlights(items);
          onChange(items);
        })
        .catch((e) => setError(e.message)),
    [lecture.id, onChange],
  );
  useEffect(() => {
    load();
  }, [load]);
  return (
    <section className="source-highlights">
      <button
        disabled={!selection || busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            await api.post("/memory", {
              kind: "highlight",
              title: selection.slice(0, 200),
              data: { lecture_id: lecture.id, content: selection },
            });
            await load();
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        ✧ Keep selected passage
      </button>
      <span>
        {selection
          ? "Selection ready to save."
          : "Select source text to keep a highlight."}
      </span>
      {highlights.length > 0 && (
        <details>
          <summary>{highlights.length} saved highlights</summary>
          {highlights.map((h) => (
            <div key={h.id}>
              <p>{h.data.content}</p>
              <button
                onClick={async () => {
                  try {
                    await api.del(`/memory/${h.id}`);
                    await load();
                  } catch (e) {
                    setError(e.message);
                  }
                }}
              >
                Remove highlight
              </button>
            </div>
          ))}
        </details>
      )}
      {error && <p role="status">{error}</p>}
    </section>
  );
}
