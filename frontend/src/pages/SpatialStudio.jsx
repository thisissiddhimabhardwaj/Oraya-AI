import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button, ErrorState, Markdown } from "../components/ui";
import { environments } from "../features/spatial/environments";
import { demoSpec } from "../features/spatial/demoSpec";
const Scene = lazy(() => import("../features/spatial/Scene"));
export default function SpatialStudio() {
  const [items, setItems] = useState([]),
    [materials, setMaterials] = useState([]),
    [record, setRecord] = useState(null),
    [topic, setTopic] = useState(""),
    [source, setSource] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState(null),
    [step, setStep] = useState(0),
    [isolated, setIsolated] = useState(false),
    [playing, setPlaying] = useState(true),
    [reset, setReset] = useState(0),
    [demo, setDemo] = useState(""),
    [question, setQuestion] = useState(""),
    [messages, setMessages] = useState([]),
    [responses, setResponses] = useState([]),
    [answers, setAnswers] = useState({}),
    [feedback, setFeedback] = useState({});
  const load = () =>
    api
      .get("/spatial")
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
    api
      .get("/lectures")
      .then((r) =>
        setMaterials(r.items.filter((m) => m.transcript_status === "ready")),
      )
      .catch((e) => setError(e.message));
  }, []);
  const adopt = (r) => {
    setRecord(r);
    setDemo("");
    setSelected(r.progress?.selected || r.scene?.objects[0]?.id || null);
    setStep(r.progress?.step || 0);
    setIsolated(r.progress?.isolated || false);
    setAnswers({});
    setFeedback({});
  };
  const open = async (id) => {
    setError("");
    try {
      adopt(await api.get(`/spatial/${id}`));
      const h = await api.get(`/spatial/${id}/history`);
      setResponses(h.responses);
      setMessages(h.messages);
    } catch (e) {
      setError(e.message);
    }
  };
  useEffect(() => {
    if (!record || !["queued", "generating"].includes(record.status)) return;
    const id = setInterval(async () => {
      try {
        const r = await api.get(`/spatial/${record.id}`);
        if (["ready", "failed"].includes(r.status)) {
          adopt(r);
          load();
        } else setRecord(r);
      } catch (e) {
        setError(e.message);
      }
    }, 2000);
    return () => clearInterval(id);
  }, [record?.id, record?.status]);
  const spec = useMemo(
    () => (demo ? demoSpec(environments[demo]) : record?.scene),
    [demo, record?.scene],
  );
  const object =
    spec?.objects.find((o) => o.id === selected) || spec?.objects[0];
  const save = async (next = {}) => {
    if (!record || record.status !== "ready" || demo) return;
    try {
      const p = { step, selected: object?.id || null, isolated, ...next };
      await api.patch(`/spatial/${record.id}`, p);
    } catch (e) {
      setError(e.message);
    }
  };
  const generate = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      adopt(
        await api.post("/spatial", {
          topic,
          lecture_id: source ? Number(source) : null,
        }),
      );
      setMessages([]);
      setResponses([]);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="spatial-studio">
      <header className="studio-heading">
        <p className="eyebrow">
          SPATIAL STUDIO / FOLLOW AN IDEA INTO THREE DIMENSIONS
        </p>
        <h1>What would you like to understand?</h1>
        <p>
          Bring a question or a learning source. ORAYA builds a saved,
          interactive teaching scene with guided exploration and challenges.
        </p>
      </header>
      {error && <ErrorState message={error} />}
      <form className="spatial-generator" onSubmit={generate}>
        <label>
          Educational topic
          <input
            className="field"
            required
            minLength={3}
            maxLength={200}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Inside a neural network, blood circulation, recursion…"
          />
        </label>
        <label>
          Source material
          <select
            className="field"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">General topic exploration</option>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" disabled={busy}>
          {busy ? "Starting…" : "Generate environment"}
        </Button>
        <Link to="/learn/new">Upload learning material ↗</Link>
      </form>
      <div className="environment-browser">
        <h2>Your saved environments</h2>
        {items.length === 0 ? (
          <p>Your first environment starts with a topic above.</p>
        ) : (
          items.map((e) => (
            <button
              key={e.id}
              onClick={() => open(e.id)}
              aria-pressed={record?.id === e.id && !demo}
            >
              <span>
                {e.title === "New learning environment" ? e.topic : e.title}
              </span>
              <small>{e.status}</small>
            </button>
          ))
        )}
      </div>
      <details className="spatial-demos">
        <summary>Explore optional demonstrations</summary>
        <nav className="spatial-tabs" aria-label="Optional demonstrations">
          {Object.entries(environments).map(([key, e]) => (
            <button
              key={key}
              aria-pressed={demo === key}
              onClick={() => {
                setDemo(key);
                setSelected("demo-0");
                setStep(0);
                setIsolated(false);
              }}
            >
              {e.subtitle}
            </button>
          ))}
        </nav>
      </details>
      {record && !demo && record.status !== "ready" && (
        <section className="scene-generation-state" role="status">
          <span>✧</span>
          <h2>
            {record.status === "failed"
              ? "This environment needs another try."
              : record.status === "queued"
                ? "Your idea is in the queue."
                : "Building your learning environment."}
          </h2>
          <p>
            {record.status === "failed"
              ? record.error
              : "The scene is being generated and checked for safe geometry, valid relationships and source references."}
          </p>
          {record.status === "failed" && (
            <Button
              onClick={async () => {
                try {
                  adopt(await api.post(`/spatial/${record.id}/retry`, {}));
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              Retry generation
            </Button>
          )}
        </section>
      )}
      {spec && (
        <>
          <div className="spatial-layout">
            <div className="spatial-stage">
              <div className="spatial-stage-heading">
                <div>
                  <p>
                    {demo
                      ? "OPTIONAL DEMONSTRATION"
                      : record.origin === "material"
                        ? "FROM YOUR LEARNING SOURCE"
                        : "AI TOPIC EXPLORATION"}
                  </p>
                  <h2>{spec.title}</h2>
                </div>
                <button
                  aria-label="Reset view"
                  onClick={() => setReset((n) => n + 1)}
                >
                  ↺
                </button>
              </div>
              <Suspense
                fallback={
                  <p className="p-8 text-white">Opening 3D viewport…</p>
                }
              >
                <Scene
                  spec={spec}
                  selected={object?.id}
                  onSelect={(id) => {
                    setSelected(id);
                    save({ selected: id });
                  }}
                  isolated={isolated}
                  playing={playing}
                  resetKey={reset}
                  step={step}
                  onError={setError}
                />
              </Suspense>
              <div className="spatial-toolbar">
                <button
                  aria-pressed={playing}
                  onClick={() => setPlaying((x) => !x)}
                >
                  {playing ? "Pause animations" : "Play animations"}
                </button>
                <button
                  aria-pressed={isolated}
                  onClick={() => {
                    setIsolated((x) => !x);
                    save({ isolated: !isolated });
                  }}
                >
                  {isolated ? "Show all objects" : "Isolate selected"}
                </button>
                <span>Drag to rotate · Scroll to zoom · Right-drag to pan</span>
              </div>
            </div>
            <aside className="spatial-inspector">
              <p className="eyebrow">LOOK A LITTLE CLOSER</p>
              <h2>{object?.label}</h2>
              <p>{object?.explanation}</p>
              {object?.animation && (
                <p className="mt-3">
                  Animation: {object.animation.explanation}
                </p>
              )}
              <div className="spatial-object-list" aria-label="Objects">
                {spec.objects.map((o) => (
                  <button
                    key={o.id}
                    aria-pressed={object?.id === o.id}
                    onClick={() => {
                      setSelected(o.id);
                      save({ selected: o.id });
                    }}
                  >
                    <i style={{ background: o.material.color }} />
                    {o.label}
                  </button>
                ))}
              </div>
              {!demo &&
                record.sources
                  ?.filter((s) => object?.source_ids?.includes(s.id))
                  .map((s) => (
                    <blockquote className="scene-source" key={s.id}>
                      <b>{s.id}</b> {s.quote}
                      <Link
                        to={`/lecture/${record.lecture_id}${s.start !== null ? `?t=${s.start}` : ""}`}
                      >
                        Open source ↗
                      </Link>
                    </blockquote>
                  ))}
            </aside>
          </div>
          <section className="spatial-lesson">
            <div>
              <p className="eyebrow">
                GUIDED EXPLORATION / {step + 1} OF {spec.steps.length}
              </p>
              <h2>{spec.steps[step]?.title}</h2>
              <p>{spec.steps[step]?.explanation}</p>
            </div>
            <Button
              variant="secondary"
              onClick={() => {
                const next = (step + 1) % spec.steps.length;
                setStep(next);
                const id = spec.steps[next]?.object_ids[0];
                setSelected(id);
                save({ step: next, selected: id });
              }}
            >
              {step === spec.steps.length - 1 ? "Begin again" : "Next step"} →
            </Button>
          </section>
          <p className="studio-notice">
            {spec.description} {spec.disclaimer}
          </p>
          {!demo && (
            <div className="spatial-learning-panels">
              <section className="studio-paper">
                <h2>Ask about this object.</h2>
                <p className="text-sm text-muted mb-4">
                  Selected: {object?.label}. Answers use this scene and its
                  supporting source.
                </p>
                {messages.map((m, i) => (
                  <article className="scene-chat-message" key={i}>
                    <b>{m.question}</b>
                    <Markdown text={m.answer} />
                  </article>
                ))}
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setBusy(true);
                    setError("");
                    try {
                      const r = await api.post(`/spatial/${record.id}/ask`, {
                        question,
                        object_id: object.id,
                      });
                      setMessages((m) => [...m, r]);
                      setQuestion("");
                    } catch (e) {
                      setError(e.message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <label className="studio-label">
                    Your question
                    <textarea
                      className="field"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      maxLength={1000}
                      required
                    />
                  </label>
                  <Button type="submit" disabled={busy}>
                    Ask scene tutor
                  </Button>
                </form>
              </section>
              <section className="studio-paper">
                <h2>Try it for yourself.</h2>
                {spec.challenges.map((c) => (
                  <article className="scene-challenge" key={c.id}>
                    <p className="eyebrow">{c.kind}</p>
                    <h3>{c.prompt}</h3>
                    {["arrange", "process"].includes(c.kind) ? (
                      <>
                        <p className="text-xs text-muted">
                          Select components in order. Select an added item to
                          remove it.
                        </p>
                        <div className="challenge-options">
                          {c.options.map((o) => (
                            <button
                              key={o}
                              aria-pressed={(answers[c.id] || []).includes(o)}
                              onClick={() =>
                                setAnswers((a) => ({
                                  ...a,
                                  [c.id]: (a[c.id] || []).includes(o)
                                    ? a[c.id].filter((x) => x !== o)
                                    : [...(a[c.id] || []), o],
                                }))
                              }
                            >
                              {spec.objects.find((x) => x.id === o)?.label || o}
                            </button>
                          ))}
                        </div>
                        <p className="text-xs my-3">
                          {(answers[c.id] || [])
                            .map(
                              (o) =>
                                spec.objects.find((x) => x.id === o)?.label ||
                                o,
                            )
                            .join(" → ")}
                        </p>
                      </>
                    ) : (
                      <div className="challenge-options">
                        {c.options.map((o) => (
                          <label key={o}>
                            <input
                              type="radio"
                              name={c.id}
                              checked={answers[c.id]?.[0] === o}
                              onChange={() =>
                                setAnswers((a) => ({ ...a, [c.id]: [o] }))
                              }
                            />
                            {spec.objects.find((x) => x.id === o)?.label || o}
                          </label>
                        ))}
                      </div>
                    )}
                    <Button
                      variant="secondary"
                      disabled={!answers[c.id]?.length || busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          const r = await api.post(
                            `/spatial/${record.id}/responses`,
                            {
                              challenge_id: c.id,
                              answer: answers[c.id],
                              submission_id: crypto.randomUUID(),
                            },
                          );
                          setFeedback((f) => ({ ...f, [c.id]: r }));
                          setResponses(
                            (await api.get(`/spatial/${record.id}/history`))
                              .responses,
                          );
                        } catch (e) {
                          setError(e.message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Check answer
                    </Button>
                    {feedback[c.id] && (
                      <p role="status" className="mt-3 text-sm">
                        {feedback[c.id].correct
                          ? "✓ Correct."
                          : "A chance to look again."}{" "}
                        {feedback[c.id].explanation}
                      </p>
                    )}
                  </article>
                ))}
                <p className="studio-notice">
                  {responses.length} saved responses ·{" "}
                  {responses.filter((r) => r.correct).length} correct.
                </p>
              </section>
            </div>
          )}
          {!demo && (
            <div className="studio-bottom">
              <p className="text-xs text-muted">
                Exploration position saves automatically.
              </p>
              <Button
                variant="secondary"
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Delete this saved environment and its exploration history?",
                    )
                  )
                    return;
                  try {
                    await api.del(`/spatial/${record.id}`);
                    setRecord(null);
                    load();
                  } catch (e) {
                    setError(e.message);
                  }
                }}
              >
                Delete environment
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
