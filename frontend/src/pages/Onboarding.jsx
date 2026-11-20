import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { Logo } from "../components/Logo";
import { Button, Chip } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const GRADES = ["Grade 9", "Grade 10", "Grade 11", "Grade 12"];
const LANGUAGES = [
  "English",
  "हिन्दी",
  "Español",
  "Français",
  "Deutsch",
  "中文",
  "العربية",
  "Português",
];
const SUBJECTS = [
  "Physics",
  "Chemistry",
  "Mathematics",
  "Biology",
  "Computer Science",
  "Economics",
];
const STRUGGLES = [
  "Understanding concepts",
  "Taking notes",
  "Staying focused",
  "Solving problems",
  "Remembering later",
  "Exam nerves",
];
const WEEKLY = ["Under 30 min", "30–60 min", "1–3 hours", "3+ hours"];
const STYLES = [
  "Animated explainers",
  "Quizzes",
  "Notes",
  "Flashcards",
  "Tutor chat",
];

function Dots({ step }) {
  return (
    <ol className="flex items-center gap-3" aria-label={`Step ${step} of 3`}>
      {[1, 2, 3].map((n) => (
        <li key={n} className="flex items-center gap-3">
          <span
            className={`block h-3.5 w-3.5 rounded-full ${
              n === step
                ? "bg-coral"
                : n < step
                  ? "bg-coral/35"
                  : "border-2 border-line2 bg-surface"
            }`}
            aria-hidden="true"
          />
          {n < 3 && (
            <span
              className="block h-px w-10 bg-line2 sm:w-14"
              aria-hidden="true"
            />
          )}
        </li>
      ))}
    </ol>
  );
}

function TelescopeArt() {
  return (
    <svg
      viewBox="0 0 420 340"
      className="w-full max-w-md"
      role="img"
      aria-label="Illustration of a student looking through a telescope"
    >
      <defs>
        <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
          <path d="M26 0H0v26" fill="none" stroke="#E4DFD6" strokeWidth="1" />
        </pattern>
      </defs>
      <rect
        x="8"
        y="120"
        width="150"
        height="150"
        fill="url(#grid)"
        opacity="0.9"
        rx="8"
      />

      {/* sparkles */}
      <g stroke="#E8705B" strokeWidth="6" strokeLinecap="round">
        <path d="M300 34 L306 14" />
        <path d="M334 52 L352 40" />
        <path d="M268 44 L256 24" />
      </g>
      <g stroke="#4C5BD4" strokeWidth="6" strokeLinecap="round">
        <path d="M366 118 L388 108" />
        <path d="M372 150 L394 152" />
      </g>

      {/* telescope */}
      <g transform="rotate(-18 300 170)">
        <rect
          x="216"
          y="146"
          width="170"
          height="52"
          rx="26"
          fill="#FBFAF7"
          stroke="#1B1B1A"
          strokeWidth="6"
        />
        <rect
          x="344"
          y="140"
          width="44"
          height="64"
          rx="14"
          fill="#E8705B"
          stroke="#1B1B1A"
          strokeWidth="6"
        />
        <circle
          cx="248"
          cy="172"
          r="16"
          fill="#E8F0E5"
          stroke="#1B1B1A"
          strokeWidth="6"
        />
      </g>

      {/* tripod */}
      <g stroke="#1B1B1A" strokeWidth="7" strokeLinecap="round" fill="none">
        <path d="M282 214 L258 316" />
        <path d="M292 214 L330 316" />
        <path d="M286 214 L288 316" />
      </g>

      {/* student */}
      <g>
        <path
          d="M60 322 C64 258 96 232 136 232 C176 232 204 258 208 322 Z"
          fill="#8FA9DE"
          stroke="#1B1B1A"
          strokeWidth="6"
        />
        <circle
          cx="146"
          cy="196"
          r="44"
          fill="#F7F4EF"
          stroke="#1B1B1A"
          strokeWidth="6"
        />
        <path
          d="M104 190 C104 150 132 138 156 144 C184 150 192 172 188 190 C180 176 164 170 148 174 C132 178 116 182 104 190 Z"
          fill="#1B1B1A"
        />
        <path
          d="M160 198 q10 8 20 0"
          stroke="#1B1B1A"
          strokeWidth="5"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M132 214 q14 10 30 2"
          stroke="#E8705B"
          strokeWidth="5"
          fill="none"
          strokeLinecap="round"
        />
        {/* arm reaching to telescope */}
        <path
          d="M186 258 C226 246 250 226 268 208"
          stroke="#1B1B1A"
          strokeWidth="7"
          fill="none"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}

function StepShell({
  step,
  title,
  children,
  onBack,
  onNext,
  nextLabel = "Continue",
  canNext = true,
  loading,
}) {
  const headingRef = useRef(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  return (
    <div>
      <p className="eyebrow">Step {step} of 3</p>
      <div className="mt-3">
        <Dots step={step} />
      </div>
      <h2
        ref={headingRef}
        tabIndex={-1}
        className="mt-8 font-display text-2xl font-bold sm:text-3xl"
      >
        {title}
      </h2>
      <div className="mt-5">{children}</div>

      <div className="mt-9 flex flex-col gap-4 sm:flex-row sm:items-center">
        <Button
          onClick={onNext}
          disabled={!canNext}
          loading={loading}
          size="lg"
          className="sm:flex-1"
        >
          {nextLabel}
          {!loading && <ArrowRight className="h-5 w-5" aria-hidden="true" />}
        </Button>
      </div>
      <button
        type="button"
        onClick={onBack}
        className="link-underline mt-5 inline-flex items-center gap-1.5 text-sm font-bold"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back
      </button>
    </div>
  );
}

function Question({ children }) {
  return <h3 className="mb-3 text-base font-bold sm:text-lg">{children}</h3>;
}

export default function Onboarding() {
  const { user, updateProfile } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [grade, setGrade] = useState(user?.grade || "");
  const [language, setLanguage] = useState(user?.language || "English");
  const [subjects, setSubjects] = useState(
    user?.subjects?.length ? user.subjects : [],
  );
  const [struggles, setStruggles] = useState(user?.prefs?.struggles || []);
  const [weekly, setWeekly] = useState(user?.prefs?.weekly || "");
  const [goals, setGoals] = useState(user?.prefs?.goals || "");
  const [examDate, setExamDate] = useState(user?.prefs?.exam_date || "");
  const [dailyMinutes, setDailyMinutes] = useState(
    user?.prefs?.daily_minutes || 30,
  );
  const [priorities, setPriorities] = useState(user?.prefs?.priorities || "");
  const [styles, setStyles] = useState(user?.prefs?.styles || []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const toggle = (list, setList, value, max) => {
    setError("");
    setList((prev) => {
      if (prev.includes(value)) return prev.filter((v) => v !== value);
      if (max && prev.length >= max) return prev;
      return [...prev, value];
    });
  };

  const finish = async () => {
    setSaving(true);
    setError("");
    try {
      await updateProfile({
        grade,
        language,
        subjects,
        prefs: {
          struggles,
          weekly,
          styles,
          goals,
          exam_date: examDate,
          daily_minutes: Number(dailyMinutes),
          priorities,
          onboarded: true,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        },
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err.message || "Couldn't save your setup");
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream">
      <header className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Logo size="md" />
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="link-underline text-sm font-bold"
        >
          Skip for now
        </button>
      </header>

      <main className="mx-auto grid max-w-7xl items-start gap-10 px-4 pb-16 sm:px-6 lg:grid-cols-2 lg:gap-16">
        <section className="pt-4">
          <h1 className="font-display text-4xl leading-[1.05] font-extrabold tracking-tight sm:text-5xl">
            Let’s start
            <br />
            with{" "}
            <span className="relative inline-block">
              you.
              <svg
                className="absolute -bottom-1.5 left-0 h-2.5 w-full text-coral"
                viewBox="0 0 120 10"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path
                  d="M4 6 C 36 1, 84 1, 116 5"
                  stroke="currentColor"
                  strokeWidth="5"
                  fill="none"
                  strokeLinecap="round"
                />
              </svg>
            </span>
          </h1>
          <p className="mt-5 max-w-md text-lg text-muted">
            A few choices. A learning space that fits.
          </p>
          <div className="mt-6 hidden lg:block">
            <TelescopeArt />
          </div>
        </section>

        <section className="card p-6 sm:p-9" aria-live="polite">
          {error && (
            <div
              role="alert"
              className="mb-5 rounded-xl border border-danger/30 bg-[#fdecec] p-4 text-sm font-medium text-danger"
            >
              {error}
            </div>
          )}

          {step === 1 && (
            <StepShell
              step={1}
              title="What grade are you in?"
              onBack={() => navigate("/")}
              onNext={() => setStep(2)}
              canNext={true}
            >
              <div
                className="flex flex-wrap gap-2.5"
                role="group"
                aria-label="Grade"
              >
                {GRADES.map((g) => (
                  <Chip
                    key={g}
                    selected={grade === g}
                    onClick={() => {
                      setGrade(g);
                      setError("");
                    }}
                  >
                    {g}
                  </Chip>
                ))}
              </div>

              <div className="mt-7">
                <label
                  htmlFor="language"
                  className="mb-2 block text-base font-bold"
                >
                  Learning language
                </label>
                <select
                  id="language"
                  className="field"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  {LANGUAGES.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-7">
                <Question>What’s your preferred subject?</Question>
                <div
                  className="flex flex-wrap gap-2.5"
                  role="group"
                  aria-label="Preferred subjects"
                >
                  {SUBJECTS.map((s) => (
                    <Chip
                      key={s}
                      selected={subjects.includes(s)}
                      aria-pressed={subjects.includes(s)}
                      onClick={() => toggle(subjects, setSubjects, s, 3)}
                    >
                      {subjects.includes(s) && (
                        <Check className="h-4 w-4" aria-hidden="true" />
                      )}
                      {s}
                    </Chip>
                  ))}
                </div>
                <p className="mt-2 text-xs text-muted">Pick up to three.</p>
              </div>
            </StepShell>
          )}

          {step === 2 && (
            <StepShell
              step={2}
              title="Where do you usually get stuck?"
              onBack={() => setStep(1)}
              onNext={() => setStep(3)}
            >
              <div
                className="flex flex-wrap gap-2.5"
                role="group"
                aria-label="Struggles"
              >
                {STRUGGLES.map((s) => (
                  <Chip
                    key={s}
                    selected={struggles.includes(s)}
                    onClick={() => toggle(struggles, setStruggles, s, 4)}
                  >
                    {struggles.includes(s) && (
                      <Check className="h-4 w-4" aria-hidden="true" />
                    )}
                    {s}
                  </Chip>
                ))}
              </div>

              <div className="mt-7">
                <Question>How much time do you have each week?</Question>
                <div
                  className="flex flex-wrap gap-2.5"
                  role="group"
                  aria-label="Weekly time"
                >
                  {WEEKLY.map((w) => (
                    <Chip
                      key={w}
                      selected={weekly === w}
                      onClick={() => setWeekly(w)}
                    >
                      {w}
                    </Chip>
                  ))}
                </div>
              </div>
            </StepShell>
          )}

          {step === 3 && (
            <StepShell
              step={3}
              title="How do you like to learn?"
              onBack={() => setStep(2)}
              onNext={finish}
              nextLabel="Enter my space"
              loading={saving}
            >
              <div
                className="flex flex-wrap gap-2.5"
                role="group"
                aria-label="Learning styles"
              >
                {STYLES.map((s) => (
                  <Chip
                    key={s}
                    selected={styles.includes(s)}
                    onClick={() => toggle(styles, setStyles, s, 4)}
                  >
                    {styles.includes(s) && (
                      <Check className="h-4 w-4" aria-hidden="true" />
                    )}
                    {s}
                  </Chip>
                ))}
              </div>

              <div className="mt-6 grid gap-3">
                <label className="text-sm">
                  Academic goal (optional)
                  <input
                    className="field mt-1"
                    value={goals}
                    onChange={(e) => setGoals(e.target.value)}
                    placeholder="What would you like to understand?"
                    maxLength={500}
                  />
                </label>
                <label className="text-sm">
                  Exam date (optional)
                  <input
                    type="date"
                    className="field mt-1"
                    value={examDate}
                    onChange={(e) => setExamDate(e.target.value)}
                  />
                </label>
                <label className="text-sm">
                  Daily study minutes
                  <input
                    type="number"
                    min="5"
                    max="480"
                    className="field mt-1"
                    value={dailyMinutes}
                    onChange={(e) => setDailyMinutes(e.target.value)}
                  />
                </label>
                <label className="text-sm">
                  Current priority (optional)
                  <input
                    className="field mt-1"
                    value={priorities}
                    onChange={(e) => setPriorities(e.target.value)}
                    maxLength={500}
                  />
                </label>
              </div>
              <div className="mt-7 rounded-2xl border border-line bg-surface2 p-5">
                <p className="eyebrow">Your setup</p>
                <ul className="mt-2 space-y-1.5 text-sm">
                  <li>
                    <span className="font-bold">{grade || "No grade yet"}</span>{" "}
                    · {language}
                  </li>
                  <li className="text-muted">
                    {subjects.length
                      ? subjects.join(", ")
                      : "No subject picked"}{" "}
                    · {weekly || "time flexible"}
                  </li>
                  <li className="text-muted">
                    {styles.length ? styles.join(", ") : "Everything, then"}
                  </li>
                </ul>
              </div>
            </StepShell>
          )}
        </section>
      </main>
    </div>
  );
}
