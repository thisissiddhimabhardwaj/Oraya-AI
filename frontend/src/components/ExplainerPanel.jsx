import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clapperboard,
  Clock,
  Download,
  FileText,
  Film,
  Play,
  RefreshCw,
  Sparkles,
  Volume2,
} from "lucide-react";
import { api } from "../lib/api";
import { Badge, Button, ErrorState } from "./ui";
import { hasActiveVideoJobs, pollVideoJobs } from "../lib/videoJobPolling";

const STAGE_LABELS = {
  queued: "Queued",
  generating_script: "Writing source-grounded script",
  generating_visuals: "Drawing educational scenes",
  generating_audio: "Recording narration",
  rendering: "Rendering and validating MP4",
  completed: "Video ready",
  failed: "Generation failed",
  render_skipped: "Previous render incomplete",
};

const PIPELINE_STAGES = [
  { key: "queued", label: "Queued", icon: Clock },
  { key: "generating_script", label: "Script", icon: FileText },
  { key: "generating_visuals", label: "Visuals", icon: Film },
  { key: "generating_audio", label: "Audio", icon: Volume2 },
  { key: "rendering", label: "Render", icon: Clapperboard },
  { key: "completed", label: "Ready", icon: CheckCircle2 },
];

function getStageIndex(status) {
  if (status === "completed") return 5;
  if (status === "rendering") return 4;
  if (status === "generating_audio") return 3;
  if (status === "generating_visuals") return 2;
  if (status === "generating_script") return 1;
  if (status === "queued") return 0;
  return -1;
}

function Video({ job }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setLoading(true);
    setError("");

    api
      .blob(`/video-jobs/${job.id}/download?kind=mp4`)
      .then((b) => {
        if (active) {
          objectUrl = URL.createObjectURL(b);
          setUrl(objectUrl);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setLoading(false);
        }
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [job.id]);

  if (error) {
    return (
      <div className="rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-xs text-danger" role="alert">
        <p className="font-semibold">Unable to load video playback</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  if (loading || !url) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center rounded-xl bg-forest/10 p-6 text-center text-muted">
        <div className="typing-indicator mb-2">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
        <p className="text-xs font-medium">Preparing validated video for playback…</p>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-xl bg-ink shadow-lg">
      <video
        className="block aspect-video w-full rounded-xl bg-ink"
        controls
        preload="metadata"
        src={url}
        aria-label={`Explainer video: ${job.concept}`}
      />
    </div>
  );
}

export function ExplainerPanel({ lecture }) {
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [concept, setConcept] = useState("");
  const [complexity, setComplexity] = useState("beginner");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showExcerptMode, setShowExcerptMode] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get("/video-jobs");
    const mine = (r.items || []).filter((j) => j.lecture_id === lecture.id);
    setJobs(mine);
    setSelected((previous) =>
      previous ? mine.find((j) => j.id === previous.id) || previous : mine[0] || null,
    );
  }, [lecture.id]);

  const active = hasActiveVideoJobs(jobs, lecture.id);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  useEffect(() => {
    if (!active) return;
    return pollVideoJobs(load, (e) => setError(e.message));
  }, [load, active]);

  const handleCreate = async (isExcerpt = false) => {
    setBusy(true);
    setError("");
    try {
      const payload = {
        concept: (concept.trim() || lecture.title).slice(0, 255),
        complexity,
        ...(isExcerpt ? { source_excerpt: true } : {}),
      };
      const j = await api.post(`/lectures/${lecture.id}/explainer-videos`, payload);
      setSelected(j);
      setJobs((prev) => [j, ...prev.filter((item) => item.id !== j.id)]);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const currentStageIdx = selected ? getStageIndex(selected.status) : -1;

  return (
    <div className="explainer-studio space-y-6">
      <header className="border-b border-line pb-4">
        <div className="flex items-center gap-2 text-coral">
          <Clapperboard size={18} aria-hidden="true" />
          <p className="eyebrow tracking-wider text-coral">AI Explainer Studio</p>
        </div>
        <h2 className="mt-1 font-serif text-2xl font-bold tracking-tight text-ink md:text-3xl">
          Visual scene-based learning.
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-muted md:text-sm">
          Source-grounded narration, pedagogical illustrations and subtitles, rendered into a real, validated MP4 video.
        </p>
      </header>

      {/* Creation form card */}
      <div className="glass-surface rounded-2xl border border-line/80 p-5 shadow-sm transition-all hover:border-line">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleCreate(false);
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="sm:col-span-2">
              <label htmlFor="explainer-concept" className="block text-xs font-bold text-ink">
                Concept or topic to explain
              </label>
              <input
                id="explainer-concept"
                className="field mt-1.5 w-full text-sm"
                required
                minLength={3}
                maxLength={255}
                value={concept}
                onChange={(e) => setConcept(e.target.value)}
                placeholder="e.g. Newton's Third Law, Mitosis, Supply & Demand…"
              />
            </div>
            <div>
              <label htmlFor="explainer-depth" className="block text-xs font-bold text-ink">
                Explanation depth
              </label>
              <select
                id="explainer-depth"
                className="field mt-1.5 w-full text-sm capitalize"
                value={complexity}
                onChange={(e) => setComplexity(e.target.value)}
              >
                {["beginner", "intermediate", "advanced"].map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-2">
              <Button
                type="submit"
                disabled={busy || lecture.transcript_status !== "ready"}
                className="shadow-sm"
              >
                <Sparkles size={15} aria-hidden="true" />
                {busy ? "Queuing video generation…" : "Generate AI Explainer"}
              </Button>
              <button
                type="button"
                onClick={() => setShowExcerptMode((prev) => !prev)}
                className="text-xs font-medium text-muted hover:text-ink underline transition-colors"
              >
                {showExcerptMode ? "Hide excerpt option" : "Source excerpt mode"}
              </button>
            </div>

            {lecture.transcript_status !== "ready" && (
              <span className="text-xs text-muted">
                (Upload transcript to enable video generation)
              </span>
            )}
          </div>

          {showExcerptMode && (
            <div className="mt-3 rounded-xl border border-dashed border-line bg-surface2/60 p-3.5 text-xs">
              <p className="font-semibold text-ink">Narrated Source Excerpts (Direct)</p>
              <p className="mt-1 text-muted">
                Reads direct excerpts from your lecture transcript with illustrated scene cards. Does not generate new text.
              </p>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || lecture.transcript_status !== "ready"}
                onClick={() => handleCreate(true)}
                className="mt-3"
              >
                <FileText size={14} aria-hidden="true" />
                Render narrated excerpts
              </Button>
            </div>
          )}
        </form>
      </div>

      {error && <ErrorState message={error} />}

      {/* Jobs selector pills */}
      {jobs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-muted">
              Generated Videos ({jobs.length})
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {jobs.map((j) => {
              const isDone = j.status === "completed";
              const isErr = ["failed", "render_skipped"].includes(j.status);
              return (
                <button
                  key={j.id}
                  type="button"
                  aria-pressed={selected?.id === j.id}
                  onClick={() => setSelected(j)}
                  className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-left text-xs transition-all ${
                    selected?.id === j.id
                      ? "border-forest bg-forest/10 font-bold text-forest shadow-sm"
                      : "border-line bg-surface hover:border-line2 text-ink"
                  }`}
                >
                  <span className="max-w-[180px] truncate">{j.concept}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      isDone
                        ? "bg-sage/30 text-sage-ink"
                        : isErr
                          ? "bg-danger/10 text-danger"
                          : "bg-coral/15 text-coral-dark"
                    }`}
                  >
                    {STAGE_LABELS[j.status] || j.status}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Active selected job detail */}
      {selected && (
        <section className="glass-surface space-y-5 rounded-2xl border border-line p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line/60 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <Badge
                  tone={
                    selected.status === "completed"
                      ? "success"
                      : ["failed", "render_skipped"].includes(selected.status)
                        ? "danger"
                        : "warn"
                  }
                >
                  {STAGE_LABELS[selected.status] || selected.status}
                </Badge>
                {selected.script_mode === "source_excerpt" && (
                  <Badge tone="neutral">Source excerpts</Badge>
                )}
                <span className="text-[11px] text-muted">
                  Job #{selected.id}
                </span>
              </div>
              <h3 className="mt-1.5 font-serif text-xl font-bold text-ink">
                {selected.concept}
              </h3>
            </div>

            {selected.status === "completed" && selected.video_url && (
              <div className="flex items-center gap-2">
                <Button
                  onClick={() =>
                    api
                      .download(
                        `/video-jobs/${selected.id}/download?kind=mp4`,
                        `oraya-${selected.concept.toLowerCase().replace(/\s+/g, "-")}.mp4`,
                      )
                      .catch((e) => setError(e.message))
                  }
                  className="text-xs"
                >
                  <Download size={14} aria-hidden="true" />
                  Download MP4
                </Button>
                <Button
                  variant="secondary"
                  onClick={() =>
                    api
                      .download(
                        `/video-jobs/${selected.id}/download?kind=srt`,
                        `oraya-${selected.concept.toLowerCase().replace(/\s+/g, "-")}.srt`,
                      )
                      .catch((e) => setError(e.message))
                  }
                  className="text-xs"
                >
                  <FileText size={14} aria-hidden="true" />
                  Subtitles (.srt)
                </Button>
              </div>
            )}
          </div>

          {/* Interactive Pipeline Stage Progress */}
          <div className="space-y-2">
            <div className="grid grid-cols-6 gap-1 text-center">
              {PIPELINE_STAGES.map((st, i) => {
                const isPassed = currentStageIdx > i || selected.status === "completed";
                const isCurrent = currentStageIdx === i && selected.status !== "completed";
                const StageIcon = st.icon;
                return (
                  <div
                    key={st.key}
                    className={`flex flex-col items-center gap-1.5 rounded-lg p-2 transition-all ${
                      isCurrent
                        ? "bg-coral/10 font-bold text-coral-dark"
                        : isPassed
                          ? "text-forest"
                          : "text-muted/60"
                    }`}
                  >
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${
                        isCurrent
                          ? "bg-coral text-white pulse-stage shadow-sm"
                          : isPassed
                            ? "bg-sage/40 text-sage-ink font-bold"
                            : "bg-surface2 text-muted/60 border border-line"
                      }`}
                    >
                      <StageIcon size={14} />
                    </div>
                    <span className="text-[10px] hidden sm:inline">{st.label}</span>
                  </div>
                );
              })}
            </div>

            {!["completed", "failed", "render_skipped"].includes(selected.status) && (
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>{selected.stage || "Processing scenes…"}</span>
                  <span className="font-bold">{selected.progress || 10}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-surface2 border border-line">
                  <div
                    className="h-full bg-coral transition-all duration-500 ease-out"
                    style={{ width: `${Math.max(8, selected.progress || 10)}%` }}
                  />
                </div>
                <p className="text-[11px] text-muted">
                  Rendering runs in bounded background workers. You can switch tabs or return later.
                </p>
              </div>
            )}
          </div>

          {/* Completed video player */}
          {selected.status === "completed" && selected.video_url && (
            <div className="space-y-3 pt-2">
              <Video job={selected} />
            </div>
          )}

          {/* Failed job recovery */}
          {["failed", "render_skipped"].includes(selected.status) && (
            <div className="rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-xs">
              <div className="flex items-start gap-2.5">
                <AlertCircle size={18} className="text-danger shrink-0 mt-0.5" />
                <div className="space-y-2">
                  <p className="font-bold text-danger">Video creation did not finish</p>
                  <p className="text-ink/80">
                    {selected.error || "The background rendering step timed out or encountered an issue."}
                  </p>
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      try {
                        const job = await api.post(`/video-jobs/${selected.id}/retry`, {});
                        setSelected(job);
                        setJobs((prev) =>
                          prev.map((item) => (item.id === job.id ? job : item)),
                        );
                        await load();
                      } catch (e) {
                        setError(e.message);
                      }
                    }}
                    className="text-xs mt-2"
                  >
                    <RefreshCw size={13} aria-hidden="true" />
                    Retry video rendering
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Floating script scene cards */}
          {selected.script && selected.script.scenes && (
            <div className="border-t border-line/60 pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-muted">
                  Video Storyboard ({selected.script.scenes.length} Scenes)
                </span>
                <span className="text-[11px] text-muted">
                  Narration: {selected.script.narration_provider || "macOS Samantha"}
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {selected.script.scenes.map((s, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl border border-line bg-surface p-3.5 text-xs shadow-sm transition-all hover:border-line2"
                  >
                    <div className="flex items-center justify-between border-b border-line/50 pb-2">
                      <span className="font-bold text-coral">Scene {idx + 1}</span>
                      <span className="rounded bg-surface2 px-1.5 py-0.5 text-[10px] font-medium text-muted">
                        {s.type || "diagram"}
                      </span>
                    </div>
                    <p className="mt-2 font-semibold text-ink">{s.heading}</p>
                    <p className="mt-1 text-muted leading-relaxed line-clamp-3">
                      {s.narration}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
