import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Clapperboard,
  FileUp,
  Link2,
  Sparkles,
} from "lucide-react";
import { Button, ErrorState, Field } from "../components/ui";
import { api } from "../lib/api";

const SAMPLE_HINTS = [
  "https://www.youtube.com/watch?v=…",
  "https://youtu.be/…",
  "https://www.youtube.com/shorts/…",
];

export default function NewLecture() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    const trimmed = url.trim();
    if (!trimmed) {
      setFieldError("Paste a YouTube link to continue");
      return;
    }
    if (!/youtu\.?be|youtube\.com/i.test(trimmed)) {
      setFieldError("That doesn't look like a YouTube link");
      return;
    }
    setFieldError("");
    setLoading(true);
    try {
      const lecture = await api.post("/lectures", { url: trimmed });
      navigate(`/lecture/${lecture.id}`);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <span className="eyebrow">New lecture</span>
      <h1 className="mt-2 font-display text-3xl font-extrabold sm:text-4xl">
        Which lecture are we unlocking?
      </h1>
      <p className="mt-3 max-w-xl text-muted">
        Paste a YouTube link. ORAYA validates it, pulls the title and thumbnail,
        and tries to fetch the transcript — you can always upload captions
        yourself if it can’t.
      </p>

      <section className="upload-material-panel">
        <span>01 / BRING YOUR OWN MATERIAL</span>
        <h2>A document. A world of possibilities.</h2>
        <p>
          Upload PDF, text, Markdown, SRT, or VTT. Text-based PDFs only; maximum
          10 MB. Files are extracted and indexed before they open.
        </p>
        <label className="upload-material-button">
          {loading ? "Extracting and indexing…" : "Choose a learning document"}
          <input
            type="file"
            accept=".pdf,.txt,.md,.srt,.vtt"
            disabled={loading}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setLoading(true);
              setError("");
              try {
                const r = await api.upload("/materials/upload", file);
                navigate(`/lecture/${r.id}`);
              } catch (err) {
                setError(err.message);
              } finally {
                setLoading(false);
              }
            }}
          />
        </label>
        {error && (
          <p role="alert" className="text-danger text-sm mt-4">
            {error}
          </p>
        )}
      </section>
      <form onSubmit={submit} noValidate className="card mt-7 p-6 sm:p-8">
        <Field
          id="url"
          label="YouTube URL"
          inputMode="url"
          autoComplete="off"
          placeholder={SAMPLE_HINTS[0]}
          value={url}
          error={fieldError}
          hint="Watch pages, youtu.be and Shorts links all work."
          onChange={(e) => {
            setUrl(e.target.value);
            if (fieldError) setFieldError("");
          }}
        />

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-sm font-medium text-danger"
          >
            {error}
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button type="submit" size="lg" loading={loading}>
            <Link2 className="h-5 w-5" aria-hidden="true" />
            Build my workspace
            {!loading && <ArrowRight className="h-5 w-5" aria-hidden="true" />}
          </Button>
          <Link to="/dashboard" className="btn btn-ghost">
            Cancel
          </Link>
        </div>
      </form>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {[
          {
            icon: Sparkles,
            title: "Metadata",
            body: "Title, channel and thumbnail fetched publicly — no API key needed.",
          },
          {
            icon: FileUp,
            title: "Captions",
            body: "Auto-fetched when possible, otherwise upload .srt / .vtt / .txt.",
          },
          {
            icon: Clapperboard,
            title: "Workspace",
            body: "Tutor, notes, quizzes and explainers attach to this lecture.",
          },
        ].map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-2xl border border-line bg-surface2 p-4"
          >
            <Icon className="h-5 w-5 text-coral" aria-hidden="true" />
            <p className="mt-2 text-sm font-bold">{title}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">{body}</p>
          </div>
        ))}
      </div>

      <p className="mt-7 text-xs text-muted">
        No video link? Upload your own notes or a text-based PDF above to start
        a reading workspace.
      </p>

      <div className="sr-only" aria-live="polite">
        {loading ? "Building your workspace" : ""}
      </div>
    </div>
  );
}
