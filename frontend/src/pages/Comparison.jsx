import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button, ErrorState } from "../components/ui";
export default function Comparison() {
  const [lectures, setLectures] = useState([]),
    [ids, setIds] = useState([]),
    [result, setResult] = useState(null),
    [semantic, setSemantic] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api
      .get("/lectures")
      .then((r) => setLectures(r.items))
      .catch((e) => setError(e.message));
  }, []);
  return (
    <div className="studio-page">
      <header className="studio-heading">
        <p className="eyebrow">UNDERSTAND · CONNECT THE DOTS</p>
        <h1>Two perspectives. A clearer picture.</h1>
        <p>
          Compare the vocabulary in your learning materials and inspect the
          passages side by side.
        </p>
      </header>
      {error && <ErrorState message={error} />}
      <form
        className="studio-paper"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            setResult(
              await api.post("/materials/compare", { lecture_ids: ids }),
            );
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset className="studio-fieldset">
          <legend>Choose 2–4 materials</legend>
          {lectures.map((l) => (
            <label className="studio-check" key={l.id}>
              <input
                type="checkbox"
                checked={ids.includes(l.id)}
                disabled={ids.length >= 4 && !ids.includes(l.id)}
                onChange={(e) =>
                  setIds(
                    e.target.checked
                      ? [...ids, l.id]
                      : ids.filter((i) => i !== l.id),
                  )
                }
              />
              {l.title}
            </label>
          ))}
        </fieldset>
        <Button type="submit" disabled={busy || ids.length < 2}>
          {busy ? "Comparing…" : "Find connections"}
        </Button>
        <Button
          variant="secondary"
          className="ml-3"
          disabled={busy || ids.length < 2}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              setSemantic(
                await api.post("/materials/compare/ai", { lecture_ids: ids }),
              );
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Compare explanations with AI
        </Button>
      </form>
      {semantic && (
        <section>
          <p className="studio-notice">{semantic.notice}</p>
          {semantic.claims.length === 0 && (
            <p>No supported comparison claims were returned.</p>
          )}
          {semantic.claims.map((c, i) => (
            <section className="comparison-row" key={i}>
              <p className="eyebrow">{c.relation}</p>
              <h2>{c.summary}</h2>
              <div>
                {c.evidence.map((e, j) => (
                  <article key={j}>
                    <Link
                      to={`/lecture/${e.lecture_id}${e.start !== null ? `?t=${e.start}` : ""}`}
                    >
                      {e.title} ↗
                    </Link>
                    <blockquote>{e.quote}</blockquote>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </section>
      )}
      {result && (
        <>
          <p className="studio-notice">
            {result.method} {result.notice}
          </p>
          {result.common.length === 0 && (
            <p>No shared terms were found in the selected materials.</p>
          )}
          {result.common.map((c) => (
            <section className="comparison-row" key={c.term}>
              <h2>{c.term}</h2>
              <div>
                {c.evidence.map((e) => (
                  <article key={e.lecture_id}>
                    <Link
                      to={`/lecture/${e.lecture_id}${e.start !== null ? `?t=${e.start}` : ""}`}
                    >
                      {e.title} ↗
                    </Link>
                    <blockquote>{e.quote}</blockquote>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
