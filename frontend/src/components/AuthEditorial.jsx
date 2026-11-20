import "./LearningUniverse.css";
import LearningUniverse from "./LearningUniverse";
export default function AuthEditorial() {
  return (
    <aside className="auth-editorial">
      <p className="landing-eyebrow">A NEW CHAPTER STARTS WITH CURIOSITY</p>
      <h2>
        Big questions.
        <br />
        Little discoveries.
        <br />
        <em>Endless possibilities.</em>
      </h2>
      <LearningUniverse compact />
      <p className="auth-editorial-caption">
        Your space to discover, understand, explore, and grow.
        <br />
        ORAYA — Beyond the Classroom.
      </p>
    </aside>
  );
}
