import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Play,
  BookOpen,
  Sparkles,
  Layers,
  Compass,
  Check,
  Plus,
} from "lucide-react";
import LearningUniverse from "../components/LearningUniverse";
import "./Landing.css";

/* Hook: adds `.lp-visible` to any `.lp-animate*` elements as they scroll into view */
function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(
      ".lp-animate, .lp-animate-left, .lp-animate-right"
    );
    if (!els.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("lp-visible");
            observer.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
}
const Arrow = () => <ArrowRight size={17} />;
function Caption({ n, children }) {
  return (
    <p className="lp-caption">
      <span>{n}</span>
      {children}
    </p>
  );
}
function Preview() {
  const [tab, setTab] = useState("Transcript");
  return (
    <div className="lp-workspace">
      <aside>
        <b>✦ ORAYA</b>
        {[
          "Your library",
          "Learning studio",
          "Smart revision",
          "Spatial studio",
        ].map((t, i) => (
          <span className={i === 1 ? "on" : ""} key={t}>
            {t}
          </span>
        ))}
        <small>A place for your curiosity.</small>
      </aside>
      <div>
        <div className="lp-workspace-top">
          <span>Biology / A world within a cell</span>
          <small>ILLUSTRATIVE PREVIEW</small>
        </div>
        <nav aria-label="Product preview tabs">
          {["Transcript", "Notes", "Questions"].map((t) => (
            <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
        <div className="lp-workspace-content">
          {tab === "Transcript" ? (
            <>
              <div className="lp-cell">
                <div className="cell-nucleus" />
                <i />
                <i />
                <i />
                <span>
                  Every small part
                  <br />
                  has a bigger purpose.
                </span>
              </div>
              <div className="lp-transcript">
                <time>01:24</time>
                <p>
                  The nucleus stores genetic information. Ribosomes use those
                  instructions to build proteins.
                </p>
                <span>Follow the words. Find the idea.</span>
              </div>
            </>
          ) : tab === "Notes" ? (
            <div className="lp-preview-notes">
              <span>01 / THE ESSENTIAL IDEA</span>
              <h3>A cell is a collaboration.</h3>
              <p>
                The nucleus stores instructions.
                <br />
                Ribosomes assemble proteins.
                <br />
                Mitochondria supply much of the cell’s ATP.
              </p>
              <hr />
              <p>
                Understanding the connections makes the parts easier to
                remember.
              </p>
            </div>
          ) : (
            <div className="lp-preview-notes">
              <span>A QUESTION WORTH ASKING</span>
              <h3>How do these parts work together?</h3>
              <p>
                Start with the source. Ask for a simpler explanation, an
                analogy, or a step-by-step view.
              </p>
              <Link to="/signup">
                Bring your own questions <ArrowUpRight size={15} />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
function OrbitalDrawing() {
  const [atom, setAtom] = useState("Oxygen");
  return (
    <div className="lp-molecule">
      <svg
        viewBox="0 0 540 370"
        role="img"
        aria-label="Schematic water molecule"
      >
        <defs>
          <radialGradient id="oxygen">
            <stop stopColor="#efb9a0" />
            <stop offset="1" stopColor="#c97964" />
          </radialGradient>
          <radialGradient id="hydrogen">
            <stop stopColor="#fff9e5" />
            <stop offset="1" stopColor="#bdc6a2" />
          </radialGradient>
        </defs>
        <path d="M70 288L438 64M95 45L465 306" stroke="#36574d" opacity=".12" />
        <ellipse
          cx="270"
          cy="190"
          rx="214"
          ry="105"
          fill="none"
          stroke="#809880"
          strokeDasharray="2 9"
          transform="rotate(-20 270 190)"
        />
        <path
          d="M270 154L142 254M270 154L398 254"
          stroke="#a8b9a5"
          strokeWidth="16"
        />
        <circle cx="270" cy="154" r="64" fill="url(#oxygen)" />
        <circle cx="142" cy="254" r="37" fill="url(#hydrogen)" />
        <circle cx="398" cy="254" r="37" fill="url(#hydrogen)" />
        <path d="M237 190Q270 230 303 190" fill="none" stroke="#57765d" />
        <text x="270" y="241" textAnchor="middle" fill="#6e8469" fontSize="12">
          104.5°
        </text>
        <text
          x="270"
          y="62"
          textAnchor="middle"
          fill="#526e58"
          fontSize="11"
          letterSpacing="3"
        >
          H₂O / A CLOSER LOOK
        </text>
      </svg>
      <div
        className="lp-atom-buttons"
        aria-label="Illustrative molecule details"
      >
        {["Oxygen", "Hydrogen"].map((x) => (
          <button key={x} onClick={() => setAtom(x)} aria-pressed={atom === x}>
            {x}
            <Plus size={12} />
          </button>
        ))}
      </div>
      <p>
        {atom === "Oxygen"
          ? "Oxygen forms two covalent bonds in a water molecule."
          : "Each hydrogen shares an electron pair with oxygen."}
      </p>
      <small>Interactive schematic · not a generated student environment</small>
    </div>
  );
}
export default function Landing() {
  useScrollReveal();
  return (
    <div className="lp" id="top">
      <a href="#lp-main" className="lp-skip">
        Skip to content
      </a>
      <nav className="lp-nav" aria-label="Main navigation">
        <Link className="lp-brand" to="/">
          <span>✦</span> ORAYA
        </Link>
        <div>
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          <a href="#students">For Students</a>
          <a href="#explore">Explore</a>
        </div>
        <section>
          <Link to="/login">Login</Link>
          <Link className="lp-button coral small" to="/signup">
            Start Learning <Arrow />
          </Link>
        </section>
      </nav>
      <main id="lp-main">
        <section className="lp-hero">
          <div className="lp-hero-copy">
            <p className="lp-eyebrow">
              BEYOND THE CLASSROOM <i />
            </p>
            <h1>
              Learning should
              <br />
              take you <em>further.</em>
            </h1>
            <p>
              Turn lectures into understanding, questions into discoveries, and
              practice into mastery.
            </p>
            <div className="lp-actions">
              <Link className="lp-button coral" to="/signup">
                Start Learning <Arrow />
              </Link>
              <a className="lp-button outline" href="#product">
                Explore ORAYA <ArrowUpRight size={16} />
              </a>
            </div>
            <div className="lp-hero-foot">
              <span>FOR THE MOMENT AN IDEA FINALLY CLICKS.</span>
              <span>01 — THE BEGINNING</span>
            </div>
          </div>
          <figure className="lp-hero-art">
            <LearningUniverse />
            <figcaption>
              A lecture is a starting point.
              <br />
              See where your curiosity takes you.
            </figcaption>
          </figure>
        </section>
        <section className="lp-problem lp-animate" id="students">
          <Caption n="01">THE PROBLEM WITH PASSIVE LEARNING</Caption>
          <h2>
            Watching is easy.
            <br />
            <span>Understanding changes everything.</span>
          </h2>
          <div className="lp-problem-bottom">
            <p>
              A video ends. A page fills with notes. But the important question
              remains: <em>did it really make sense?</em>
            </p>
            <p>
              ORAYA makes room for what comes next — the question, the
              connection, the moment it clicks.
            </p>
            <div className="lp-margin-note">
              Less “I watched it.”
              <br />
              <em>More “I get it.”</em>
              <span>↙</span>
            </div>
          </div>
        </section>
        <section className="lp-philosophy lp-animate" id="product">
          <div>
            <Caption n="02">OUR LEARNING PHILOSOPHY</Caption>
            <h2>Curiosity is the curriculum.</h2>
            <p>
              Good learning moves. From discovering an idea to understanding it,
              exploring its possibilities, and making it your own.
            </p>
          </div>
          <ol>
            {[
              [
                "I",
                "Discover & understand",
                "Bring the material. Ask the question that matters to you.",
              ],
              [
                "II",
                "Explore & practise",
                "See an idea from another angle. Put your understanding to work.",
              ],
              [
                "III",
                "Revise & master",
                "Return at the right moment. Let small reviews build lasting memory.",
              ],
            ].map(([n, t, p]) => (
              <li key={n}>
                <span>{n}</span>
                <h3>{t}</h3>
                <p>{p}</p>
              </li>
            ))}
          </ol>
        </section>
        <section className="lp-how lp-animate" id="features">
          <div className="lp-section-head">
            <div>
              <Caption n="03">HOW ORAYA WORKS</Caption>
              <h2>
                Your material.
                <br />A whole new way in.
              </h2>
            </div>
            <p>
              One connected workspace. Add a lecture or document, follow the
              source, and turn it into questions, notes, and practice.
            </p>
          </div>
          <Preview />
          <div className="lp-process">
            <span>01 &nbsp; Bring a lecture or document</span>
            <Arrow />
            <span>02 &nbsp; Follow your questions</span>
            <Arrow />
            <span>03 &nbsp; Make understanding stick</span>
          </div>
        </section>
        <section className="lp-tutor lp-animate">
          <div className="lp-tutor-visual">
            <span className="lp-side-label">A CONVERSATION WITH THE IDEA</span>
            <div className="lp-source-slip">
              <small>YOUR SOURCE / CELL BIOLOGY</small>
              <p>“Ribosomes assemble proteins by translating messenger RNA.”</p>
              <span>Source excerpt · illustrative example</span>
            </div>
            <div className="lp-question-slip">
              <Sparkles size={22} />
              <h3>
                Could you explain
                <br />
                that another way?
              </h3>
              <p>Simpler language. An analogy. One step at a time.</p>
            </div>
            <span className="lp-hand-arrow">⤵</span>
          </div>
          <div className="lp-editorial-copy">
            <Caption n="04">YOUR AI TUTOR</Caption>
            <h2>
              Stay with the question.
              <br />
              <em>That’s where it begins.</em>
            </h2>
            <p>
              Ask about the material in front of you. Get explanations grounded
              in your lecture, with source references you can return to.
            </p>
            <p>
              When an answer needs a different angle, change the explanation —
              without losing the original idea.
            </p>
            <Link className="lp-text-link" to="/signup">
              Find your way to understanding <Arrow />
            </Link>
          </div>
        </section>
        <section className="lp-notes lp-animate">
          <div className="lp-editorial-copy">
            <Caption n="05">SMART NOTES & YOUR LIBRARY</Caption>
            <h2>
              Keep the ideas.
              <br />
              Find the connections.
            </h2>
            <p>
              A home for your lectures, documents, thoughtful notes, and useful
              explanations. Search your sources. Save a passage. Write something
              in your own words.
            </p>
            <Link className="lp-text-link" to="/signup">
              Build your learning library <Arrow />
            </Link>
          </div>
          <div className="lp-notebook">
            <header>
              <BookOpen size={20} />
              <span>FIELD NOTES / AN IDEA WORTH KEEPING</span>
            </header>
            <h3>
              Small structures.
              <br />
              Extraordinary collaboration.
            </h3>
            <p>
              <mark>The nucleus stores the instructions.</mark>
              <br />
              Ribosomes build proteins.
              <br />
              Mitochondria supply energy.
            </p>
            <div className="lp-note-rule" />
            <footer>
              <span>MY OWN WORDS</span>
              <p>A cell works because its parts work together.</p>
            </footer>
            <small>Illustrative learning note</small>
          </div>
        </section>
        <section className="lp-revision lp-animate">
          <div>
            <Caption n="06">SMART REVISION</Caption>
            <h2>
              A little today.
              <br />
              Still with you tomorrow.
            </h2>
            <p>
              Answer from memory. Compare with your source. Rate your recall.
              ORAYA schedules the next review with spaced repetition — and saves
              where you left off.
            </p>
            <Link className="lp-text-link" to="/signup">
              Make room for lasting memory <Arrow />
            </Link>
          </div>
          <div className="lp-revision-figure">
            <div className="lp-recall-card">
              <small>A QUESTION TO COME BACK TO</small>
              <h3>
                Why do the parts
                <br />
                work better together?
              </h3>
              <span>Think first. Then look again.</span>
            </div>
            <div className="lp-memory-line">
              <i />
              <i />
              <i />
              <i />
              <svg viewBox="0 0 400 65" aria-hidden="true">
                <path
                  d="M5 55Q40 0 85 45T185 33T295 18T395 8"
                  stroke="#78936b"
                  strokeWidth="2"
                  fill="none"
                />
              </svg>
            </div>
            <p>Review → Recall → Revisit → Remember</p>
            <small>
              Illustration of a learning rhythm, not student performance data.
            </small>
          </div>
        </section>
        <section className="lp-explainer lp-animate">
          <div className="lp-film">
            <div className="lp-film-top">
              <span>ORAYA EXPLAINER</span>
              <span>A DIFFERENT PERSPECTIVE</span>
            </div>
            <div className="lp-film-frame">
              <div className="lp-process-visual">
                <span>Instructions</span>
                <b>→</b>
                <span>Proteins</span>
                <b>→</b>
                <span>Cell functions</span>
              </div>
              <h3>
                Give the idea
                <br />a moving picture.
              </h3>
              <p>Educational illustrations. Real narration. Subtitles.</p>
            </div>
            <div className="lp-film-bottom">
              <span>SOURCE → SCRIPT → SCENES → NARRATED MP4</span>
            </div>
          </div>
          <div className="lp-editorial-copy">
            <Caption n="07">AI EXPLAINER</Caption>
            <h2>
              Some ideas need
              <br />
              to be <em>seen.</em>
            </h2>
            <p>
              Turn source material into a scene-based educational video. Follow
              the explanation, hear the narration, and keep the finished MP4 for
              another look.
            </p>
            <p>
              Rendering progress stays visible. A video is ready only when its
              finished file has been validated.
            </p>
            <Link className="lp-text-link" to="/signup">
              See your learning differently <Arrow />
            </Link>
          </div>
        </section>
        <section className="lp-spatial lp-animate" id="explore">
          <div className="lp-editorial-copy">
            <Caption n="08">SPATIAL LEARNING STUDIO</Caption>
            <h2>
              Step inside
              <br />
              the idea.
            </h2>
            <p>
              A question can become a place to explore. Generate a learning
              environment from a topic or your own material, inspect its
              objects, and follow a guided path through the concept.
            </p>
            <p>
              Ask about what you see. Try a challenge. Save your progress and
              return with a new question.
            </p>
            <Link className="lp-button outline" to="/signup">
              Enter Spatial Studio <ArrowUpRight size={17} />
            </Link>
          </div>
          <OrbitalDrawing />
        </section>
        <section className="lp-personal lp-animate">
          <Caption n="09">PERSONALISED LEARNING</Caption>
          <h2>
            A learning space.
            <br />
            <em>Your kind of space.</em>
          </h2>
          <p>
            Your goals, preferences, saved sources, and real review history help
            shape what comes next. Inspect your learning profile and choose what
            to keep.
          </p>
          <div>
            <span>
              <Check size={16} />
              Your pace
            </span>
            <span>
              <Check size={16} />
              Your questions
            </span>
            <span>
              <Check size={16} />
              Your learning, your data
            </span>
          </div>
        </section>
        <section className="lp-final lp-animate">
          <p className="lp-eyebrow">YOUR NEXT CHAPTER</p>
          <h2>
            Ready to go beyond
            <br />
            the classroom?
          </h2>
          <Link className="lp-button coral" to="/signup">
            Start Learning <Arrow />
          </Link>
          <p>Bring your curiosity. We’ll make room for the rest.</p>
          <svg
            viewBox="0 0 1280 180"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              d="M0 160L95 99 210 131 360 51 470 118 600 170 760 138 900 30 1030 112 1180 70 1280 129V180H0Z"
              fill="#c9d4bf"
            />
            <path
              d="M0 180L120 151 260 161 440 115 650 180 850 144 1010 116 1280 153V180Z"
              fill="#a7b99a"
            />
          </svg>
        </section>
      </main>
      <footer className="lp-footer">
        <div>
          <Link className="lp-brand" to="/">
            <span>✦</span> ORAYA
          </Link>
          <p>Beyond the Classroom.</p>
        </div>
        <nav aria-label="Footer">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          <a href="#students">For Students</a>
          <a href="#explore">Explore</a>
          <Link to="/login">Your learning space ↗</Link>
        </nav>
        <span>For minds that keep wondering.</span>
      </footer>
    </div>
  );
}
