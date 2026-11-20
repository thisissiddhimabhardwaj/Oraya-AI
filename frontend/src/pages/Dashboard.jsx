import LearningPriorities from "../components/LearningPriorities";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDownRight,
  ArrowRight,
  BookOpen,
  CalendarDays,
  Check,
  Clapperboard,
  Clock3,
  Download,
  Film,
  Flame,
  Layers,
  MessageSquare,
  Play,
  Plus,
  Sparkles,
  Target,
} from "lucide-react";
import { Badge, ErrorState, ProgressBar } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import "./Dashboard.css";

const shortDate = (date) =>
  new Date(`${date}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
const durationLabel = (seconds) =>
  seconds > 0 ? `${Math.ceil(seconds / 60)} min` : null;

function SectionLink({ to, children }) {
  return (
    <Link className="dash-section-link" to={to}>
      {children}
      <ArrowRight size={15} aria-hidden="true" />
    </Link>
  );
}

function ActivityChart({ days }) {
  const [selected, setSelected] = useState(null);
  const max = Math.max(1, ...days.map((day) => day.items));
  const total = days.reduce((sum, day) => sum + day.items, 0);
  const activeDays = days.filter((day) => day.items > 0).length;
  const selectedDay = days.find((day) => day.date === selected);
  return (
    <section
      className="dash-panel dash-activity"
      aria-labelledby="activity-heading"
    >
      <div className="dash-panel-heading">
        <h2 id="activity-heading">Learning rhythm</h2>
        <span className="dash-period">14 days</span>
      </div>
      <p className="dash-activity-total">
        <strong>{activeDays}</strong>
        <span>
          active {activeDays === 1 ? "day" : "days"}
          <br />
          in the last two weeks
        </span>
      </p>
      <div
        className="dash-chart"
        role="group"
        aria-label="Daily lectures saved and quizzes attempted. Select a bar for its count."
      >
        {days.map((day, index) => (
          <button
            key={day.date}
            type="button"
            className={`dash-chart-day ${day.items > 0 ? "has-activity" : ""} ${selected === day.date ? "is-selected" : ""}`}
            aria-label={`${shortDate(day.date)}: ${day.items} ${day.items === 1 ? "activity" : "activities"}`}
            aria-pressed={selected === day.date}
            tabIndex={
              selected
                ? selected === day.date
                  ? 0
                  : -1
                : index === days.length - 1
                  ? 0
                  : -1
            }
            onFocus={() => setSelected(day.date)}
            onClick={() => setSelected(day.date)}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? Math.min(index + 1, days.length - 1)
                  : event.key === "ArrowLeft"
                    ? Math.max(index - 1, 0)
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? days.length - 1
                        : null;
              if (next !== null) {
                event.preventDefault();
                event.currentTarget.parentElement.children[next].focus();
              }
            }}
          >
            <span
              className="dash-chart-bar"
              style={{
                height:
                  day.items > 0
                    ? `${Math.max(12, (day.items / max) * 100)}%`
                    : "3px",
              }}
            />
          </button>
        ))}
      </div>
      <div className="dash-chart-labels">
        <span>{days[0] ? shortDate(days[0].date) : "Two weeks ago"}</span>
        <span>{days.length ? shortDate(days.at(-1).date) : "Today"}</span>
      </div>
      <p className="dash-chart-caption" aria-live="polite">
        {selectedDay
          ? `${shortDate(selectedDay.date)} · ${selectedDay.items} ${selectedDay.items === 1 ? "activity" : "activities"}`
          : total
            ? `${total} ${total === 1 ? "lecture saved or quiz attempted" : "lectures saved and quizzes attempted"}`
            : "Your next lecture or quiz starts the story."}
      </p>
    </section>
  );
}

function LectureArtwork({ lecture, featured = false }) {
  const [failed, setFailed] = useState(false);
  return (
    <div
      className={`dash-lecture-art ${featured ? "is-featured" : ""}`}
      aria-hidden="true"
    >
      {lecture.thumbnail && !failed ? (
        <img
          src={lecture.thumbnail}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <>
          <div className="dash-art-lines" />
          <BookOpen strokeWidth={1.4} />
        </>
      )}
      {featured && (
        <span className="dash-art-label">
          {lecture.source === "sample"
            ? "THE SAMPLE SERIES"
            : "YOUR LEARNING LIBRARY"}
        </span>
      )}
    </div>
  );
}

function DashboardLoading() {
  return (
    <div
      className="dashboard dash-loading"
      role="status"
      aria-label="Loading your dashboard"
      aria-busy="true"
    >
      <div className="dash-skeleton dash-skeleton-title" />
      <div className="dash-stats">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="dash-skeleton dash-skeleton-stat" />
        ))}
      </div>
      <div className="dash-layout">
        <div className="dash-skeleton dash-skeleton-content" />
        <div className="dash-skeleton dash-skeleton-content" />
      </div>
      <span className="sr-only">Loading your dashboard…</span>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [progress, setProgress] = useState(null);
  const [videoJobs, setVideoJobs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [progressError, setProgressError] = useState(false);

  const load = async (signal) => {
    setLoading(true);
    setError("");
    setProgressError(false);
    try {
      const [dash, prog, vids] = await Promise.allSettled([
        api.get("/dashboard", signal),
        api.get("/progress/overview", signal),
        api.get("/video-jobs", signal),
      ]);
      if (signal?.aborted) return;
      if (dash.status === "rejected") throw dash.reason;
      setData(dash.value);
      setProgress(prog.status === "fulfilled" ? prog.value : null);
      setProgressError(prog.status === "rejected");
      setVideoJobs(vids.status === "fulfilled" && vids.value?.items ? vids.value.items : []);
    } catch (err) {
      if (!signal?.aborted) setError(err.message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);

  if (loading) return <DashboardLoading />;
  if (error) return <ErrorState message={error} onRetry={() => load()} />;

  const stats = data?.stats || {};
  const lectures = data?.recent_lectures || [];
  const recommendations = progress?.recommendations || [];
  const continueHref = recommendations.find(
    (item) => item.type === "continue",
  )?.href;
  const featured =
    lectures.find((lecture) => `/lecture/${lecture.id}` === continueHref) ||
    lectures[0];
  const others = lectures.filter((lecture) => lecture.id !== featured?.id);
  const mastery = progress?.mastery || [];
  const weak = progress?.weak_topics || [];
  const nextSteps = recommendations
    .filter((item) => item.type !== "continue")
    .slice(0, 3);
  const firstName = (user?.name || user?.email || "there").split(/[\s@.]+/)[0];
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const average =
    (stats.quizzes ?? 0) > 0
      ? `${Math.round((stats.avg_score ?? 0) * 100)}%`
      : "—";
  const metrics = [
    {
      icon: BookOpen,
      label: "Lectures saved",
      value: stats.lectures ?? 0,
      detail: "A library of possibilities",
      tone: "coral",
    },
    {
      icon: Target,
      label: "Quizzes taken",
      value: stats.quizzes ?? 0,
      detail: "Turn recall into understanding",
      tone: "sage",
    },
    {
      icon: Sparkles,
      label: "Average quiz score",
      value: average,
      detail:
        (stats.quizzes ?? 0) > 0
          ? "Across all your attempts"
          : "Take a quiz to see your score",
      tone: "lavender",
    },
    {
      icon: Clock3,
      label: "Lecture minutes reached",
      value: stats.minutes_watched ?? 0,
      detail: "Saved playback positions",
      tone: "sand",
    },
  ];

  return (
    <div className="dashboard">
      <header className="dash-welcome">
        <div>
          <p className="dash-eyebrow">YOUR LEARNING SPACE</p>
          <h1>
            {greeting}, {firstName}
            <span className="dash-greeting-dot">.</span>
          </h1>
          <p>
            A little curiosity. A little practice. A little further every day.
          </p>
        </div>
        <div className="dash-date">
          <CalendarDays size={16} aria-hidden="true" />
          <time dateTime={new Date().toLocaleDateString("en-CA")}>
            {new Date().toLocaleDateString(undefined, {
              weekday: "short",
              month: "short",
              day: "numeric",
            })}
          </time>
        </div>
      </header>

      {user && !user.prefs?.onboarded && (
        <aside className="dash-setup">
          <span className="dash-icon sage">
            <Sparkles size={20} aria-hidden="true" />
          </span>
          <div>
            <strong>Make this space yours</strong>
            <p>
              Set your level and interests for a more personal learning
              experience.
            </p>
          </div>
          <SectionLink to="/onboarding">Finish setup</SectionLink>
        </aside>
      )}
      {progressError && (
        <div className="dash-notice" role="status">
          <span>Your lectures are ready. Progress insights couldn’t load.</span>
          <button type="button" onClick={() => load()}>
            Try again <ArrowRight size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      <dl className="dash-stats" aria-label="Your learning at a glance">
        {metrics.map(({ icon: Icon, label, value, detail, tone }) => (
          <div className="dash-stat card-floating" key={label}>
            <dt className="dash-stat-top">
              <span>{label}</span>
              <span className={`dash-icon ${tone}`}>
                <Icon size={18} aria-hidden="true" />
              </span>
            </dt>
            <dd>{value}</dd>
            <dd className="dash-stat-detail">{detail}</dd>
          </div>
        ))}
      </dl>

      <div className="dash-layout">
        <div className="dash-primary-column">
          <section aria-labelledby="continue-heading">
            <div className="dash-section-heading">
              <div>
                <p className="dash-eyebrow">ONE IDEA AT A TIME</p>
                <h2 id="continue-heading">
                  {featured ? "Continue learning" : "Start learning"}
                </h2>
              </div>
              <SectionLink to="/library">View library</SectionLink>
            </div>
            {featured ? (
              <article className="dash-featured">
                <div className="dash-featured-copy">
                  <div className="dash-tags">
                    <span className="dash-overline">
                      {continueHref === `/lecture/${featured.id}`
                        ? "PICK UP WHERE YOU LEFT OFF"
                        : "FROM YOUR LIBRARY"}
                    </span>
                    {featured.source === "sample" && (
                      <Badge tone="neutral">Sample lecture</Badge>
                    )}
                  </div>
                  <h3>{featured.title}</h3>
                  <p className="dash-featured-description">
                    {featured.transcript_status === "missing"
                      ? "Add a transcript to unlock notes, quizzes and your AI tutor."
                      : "Go beyond watching. Explore the ideas, ask questions and make them stick."}
                  </p>
                  <div className="dash-lecture-meta">
                    <span>
                      <BookOpen size={14} aria-hidden="true" />
                      {featured.source === "sample"
                        ? "ORAYA original"
                        : featured.channel || "Saved lecture"}
                    </span>
                    {durationLabel(featured.duration) && (
                      <span>
                        <Clock3 size={14} aria-hidden="true" />
                        {durationLabel(featured.duration)}
                      </span>
                    )}
                  </div>
                  <Link
                    className="btn dash-primary-action"
                    to={`/lecture/${featured.id}`}
                  >
                    <Play size={16} fill="currentColor" aria-hidden="true" />
                    {continueHref === `/lecture/${featured.id}`
                      ? "Continue lecture"
                      : "Open lecture"}
                    <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </div>
                <LectureArtwork key={featured.id} lecture={featured} featured />
              </article>
            ) : (
              <div className="dash-first-lecture">
                <span className="dash-icon coral">
                  <BookOpen size={26} aria-hidden="true" />
                </span>
                <h3>Big ideas start with one lecture.</h3>
                <p>
                  Save a YouTube lecture to turn it into a space for questions,
                  notes and practice.
                </p>
                <Link className="btn dash-primary-action" to="/learn/new">
                  <Plus size={18} aria-hidden="true" />
                  Add your first lecture
                </Link>
              </div>
            )}
            {others.length > 0 && (
              <div className="dash-recent-list">
                {others.map((lecture) => (
                  <Link
                    className="dash-lecture-row"
                    to={`/lecture/${lecture.id}`}
                    key={lecture.id}
                  >
                    <LectureArtwork lecture={lecture} />
                    <div className="dash-lecture-row-copy">
                      <h3>{lecture.title}</h3>
                      <p>
                        {lecture.source === "sample"
                          ? "ORAYA original"
                          : lecture.channel || "Saved lecture"}
                        {durationLabel(lecture.duration)
                          ? ` · ${durationLabel(lecture.duration)}`
                          : ""}
                      </p>
                    </div>
                    <span
                      className={`dash-transcript-status ${lecture.transcript_status === "missing" ? "is-missing" : ""}`}
                    >
                      {lecture.transcript_status === "missing" ? (
                        "Add transcript"
                      ) : (
                        <>
                          <Check size={13} aria-hidden="true" />
                          Transcript ready
                        </>
                      )}
                    </span>
                    <ArrowRight size={18} aria-hidden="true" />
                  </Link>
                ))}
              </div>
            )}
          </section>

          {featured && (
            <div className="card-floating flex flex-wrap items-center justify-between gap-4 p-5">
              <div className="flex items-center gap-3.5">
                <span className="dash-icon coral shadow-sm">
                  <MessageSquare size={20} aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-serif text-lg font-bold text-ink">
                    AI Tutor · {featured.title}
                  </h3>
                  <p className="text-xs text-muted">
                    {featured.transcript_status === "ready"
                      ? "Answers cite exact lecture timestamps with verified reasoning."
                      : "Upload transcript in the workspace to chat with the AI tutor."}
                  </p>
                </div>
              </div>
              <Link
                to={`/lecture/${featured.id}`}
                className="btn btn-secondary text-xs shrink-0"
              >
                Open Tutor <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
          )}

          {videoJobs.length > 0 && (
            <section className="dash-panel card-floating" aria-labelledby="video-status-heading">
              <div className="dash-panel-heading">
                <div className="flex items-center gap-2">
                  <span className="dash-icon lavender">
                    <Clapperboard size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <h2 id="video-status-heading" className="text-base font-bold">
                      AI Explainer Videos
                    </h2>
                    <span className="text-[11px] text-muted">
                      {videoJobs.filter((v) => v.status === "completed").length} ready to watch
                    </span>
                  </div>
                </div>
                <SectionLink to={featured ? `/lecture/${featured.id}` : "/library"}>
                  Studio
                </SectionLink>
              </div>
              <div className="mt-3 space-y-2">
                {videoJobs.slice(0, 3).map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between rounded-xl border border-line bg-surface p-3 text-xs transition-all hover:border-line2"
                  >
                    <div className="max-w-[70%] space-y-0.5">
                      <p className="font-semibold text-ink truncate">{job.concept}</p>
                      <p className="text-[11px] text-muted truncate">
                        {job.status === "completed"
                          ? "Illustrated MP4 with audio narration ready"
                          : job.stage || "Processing scenes…"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        tone={
                          job.status === "completed"
                            ? "success"
                            : ["failed", "render_skipped"].includes(job.status)
                              ? "danger"
                              : "warn"
                        }
                      >
                        {job.status === "completed" ? "Ready" : job.status}
                      </Badge>
                      {job.status === "completed" && (
                        <Link
                          to={`/lecture/${job.lecture_id}`}
                          className="rounded-full bg-forest/10 p-1.5 text-forest hover:bg-forest hover:text-white transition-colors"
                          title="Watch in workspace"
                        >
                          <Play size={13} fill="currentColor" />
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section
            className="dash-tools-section"
            aria-labelledby="tools-heading"
          >
            <div className="dash-section-heading">
              <h2 id="tools-heading">Make it stick</h2>
              <span className="dash-section-note">Your learning toolkit</span>
            </div>
            <div className="dash-tools">
              <Link
                to={featured ? `/lecture/${featured.id}` : "/library"}
                className="dash-tool"
              >
                <span className="dash-icon coral">
                  <Target size={21} aria-hidden="true" />
                </span>
                <h3>Test your understanding</h3>
                <p>Open a lecture and try a quiz on what you’ve learned.</p>
                <span className="dash-tool-link">
                  Practice a little <ArrowRight size={15} aria-hidden="true" />
                </span>
              </Link>
              <Link to="/flashcards" className="dash-tool">
                <span className="dash-icon lavender">
                  <Layers size={21} aria-hidden="true" />
                </span>
                <h3>Refresh your memory</h3>
                <p>Revisit the key ideas, one flashcard at a time.</p>
                <span className="dash-tool-link">
                  Review flashcards <ArrowRight size={15} aria-hidden="true" />
                </span>
              </Link>
            </div>
          </section>

          {nextSteps.length > 0 && (
            <section
              className="dash-panel dash-next"
              aria-labelledby="next-heading"
            >
              <div className="dash-panel-heading">
                <h2 id="next-heading">A good next step</h2>
                <ArrowDownRight size={20} aria-hidden="true" />
              </div>
              <ul>
                {nextSteps.map((item) => (
                  <li key={item.href + item.label}>
                    <Link to={item.href}>
                      <span className="dash-icon sand">
                        {item.type === "flashcards" ? (
                          <Layers size={18} aria-hidden="true" />
                        ) : item.type === "revise" ? (
                          <Target size={18} aria-hidden="true" />
                        ) : (
                          <Plus size={18} aria-hidden="true" />
                        )}
                      </span>
                      <span>{item.label}</span>
                      <ArrowRight size={17} aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data?.recent_attempts?.length > 0 && (
            <section className="dash-panel" aria-labelledby="quizzes-heading">
              <div className="dash-panel-heading">
                <h2 id="quizzes-heading">Recent practice</h2>
                <SectionLink to="/progress">All progress</SectionLink>
              </div>
              <ul className="dash-quiz-list">
                {data.recent_attempts.map((attempt) => (
                  <li key={attempt.id}>
                    <Link
                      to={
                        attempt.lecture_id
                          ? `/lecture/${attempt.lecture_id}`
                          : "/progress"
                      }
                    >
                      <span className="dash-icon sage">
                        <Target size={18} aria-hidden="true" />
                      </span>
                      <div>
                        <h3>{attempt.lecture_title}</h3>
                        <p>
                          {new Date(attempt.created_at).toLocaleDateString(
                            undefined,
                            { month: "short", day: "numeric" },
                          )}{" "}
                          · {attempt.count} questions
                        </p>
                      </div>
                      <Badge
                        tone={
                          attempt.score >= 0.7
                            ? "ok"
                            : attempt.score >= 0.4
                              ? "warn"
                              : "danger"
                        }
                      >
                        {Math.round(attempt.score * 100)}%
                      </Badge>
                      <ArrowRight size={16} aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside
          className="dash-secondary-column"
          aria-label="Your learning insights"
        >
          <ActivityChart days={data?.activity || []} />
          <section className="dash-panel" aria-labelledby="mastery-heading">
            <div className="dash-panel-heading">
              <h2 id="mastery-heading">Topic mastery</h2>
              <SectionLink to="/progress">Details</SectionLink>
            </div>
            {progressError ? (
              <p className="dash-panel-description">
                Your mastery insights will appear when progress is available
                again.
              </p>
            ) : mastery.length ? (
              <>
                <p className="dash-panel-description">
                  Topic mastery from your quiz results.
                </p>
                <ul className="dash-mastery-list">
                  {mastery.slice(0, 4).map((item) => (
                    <li key={item.topic}>
                      <div>
                        <span>{item.topic}</span>
                        <strong>{Math.round(item.score * 100)}%</strong>
                      </div>
                      <ProgressBar
                        value={item.score * 100}
                        label={`${item.topic} mastery`}
                      />
                    </li>
                  ))}
                </ul>
                {weak.length > 0 && (
                  <div className="dash-weak">
                    <Target size={16} aria-hidden="true" />
                    <p>
                      <strong>A little more practice</strong>
                      {weak.slice(0, 3).join(", ")}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="dash-mastery-empty">
                <span className="dash-mastery-symbol">
                  <Target size={30} strokeWidth={1.5} aria-hidden="true" />
                </span>
                <h3>Discover what’s clicking</h3>
                <p>
                  Take your first quiz to see what you know and where to focus
                  next.
                </p>
                <SectionLink
                  to={featured ? `/lecture/${featured.id}` : "/library"}
                >
                  Explore a lecture
                </SectionLink>
              </div>
            )}
          </section>
          {!progressError && (
            <div className="dash-streak">
              <span className="dash-streak-icon">
                <Flame size={25} aria-hidden="true" />
              </span>
              <div>
                <strong>{progress?.streak_days ?? 0}-day streak</strong>
                <p>
                  {progress?.streak_days > 0
                    ? "Small steps, steady momentum. Keep it going."
                    : "A little practice today is a great place to start."}
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
      <footer className="dash-footer">
        <span>Learn at your own pace.</span>
        <span>One idea can change how you see everything.</span>
      </footer>
      <LearningPriorities />
    </div>
  );
}
