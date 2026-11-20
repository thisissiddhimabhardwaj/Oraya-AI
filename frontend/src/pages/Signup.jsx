import AuthEditorial from "../components/AuthEditorial";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Logo } from "../components/Logo";
import { Button, Field } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const RULES = [
  { id: "len", label: "At least 8 characters", test: (v) => v.length >= 8 },
  { id: "letter", label: "One letter", test: (v) => /[a-zA-Z]/.test(v) },
  { id: "digit", label: "One number", test: (v) => /\d/.test(v) },
];

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);
  const summaryRef = useRef(null);

  useEffect(() => {
    summaryRef.current?.focus();
  }, [formError]);

  const validate = () => {
    const next = {};
    if (!name.trim()) next.name = "Tell us what to call you";
    if (!email.trim()) next.email = "Enter your email address";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      next.email = "That doesn't look like a valid email";
    const failed = RULES.filter((r) => !r.test(password));
    if (failed.length)
      next.password = `Password needs: ${failed.map((r) => r.label.toLowerCase()).join(", ")}`;
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    setFormError("");
    if (!validate()) return;
    setLoading(true);
    try {
      await signup(email.trim(), password, name.trim());
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setFormError(err.message || "Could not create your account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <AuthEditorial />
      <div className="auth-form-column">
        <div className="mb-8 flex justify-center">
          <Link to="/" aria-label="ORAYA home">
            <Logo size="md" />
          </Link>
        </div>

        <div className="card p-6 sm:p-8">
          <h1 className="font-display text-3xl font-bold">Create your space</h1>
          <p className="mt-1.5 text-sm text-muted">
            Twenty seconds, then straight into learning.
          </p>

          {formError && (
            <div
              ref={summaryRef}
              tabIndex={-1}
              role="alert"
              aria-labelledby="signup-error-title"
              className="mt-5 rounded-xl border border-danger/30 bg-[#fdecec] p-4"
            >
              <p
                id="signup-error-title"
                className="text-sm font-bold text-danger"
              >
                There is a problem
              </p>
              <p className="mt-1 text-sm text-danger">{formError}</p>
            </div>
          )}

          <form onSubmit={submit} noValidate className="mt-6 space-y-4">
            <Field
              id="name"
              label="Your name"
              autoComplete="name"
              placeholder="Alex Rivera"
              value={name}
              error={errors.name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => validate()}
            />
            <Field
              id="email"
              label="Email"
              type="email"
              autoComplete="email"
              placeholder="you@school.edu"
              value={email}
              error={errors.email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => validate()}
            />
            <div>
              <Field
                id="password"
                label="Password"
                type="password"
                autoComplete="new-password"
                placeholder="••••••••"
                value={password}
                error={errors.password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => validate()}
              />
              <ul className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
                {RULES.map((rule) => {
                  const ok = rule.test(password);
                  return (
                    <li
                      key={rule.id}
                      className={`flex items-center gap-1.5 text-xs font-semibold ${ok ? "text-ok" : "text-muted"}`}
                    >
                      <CheckCircle2
                        className={`h-3.5 w-3.5 ${ok ? "opacity-100" : "opacity-35"}`}
                        aria-hidden="true"
                      />
                      {rule.label}
                      <span className="sr-only">
                        {ok ? " (met)" : " (not met)"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>

            <Button
              type="submit"
              loading={loading}
              className="w-full"
              size="lg"
            >
              Sign up
              {!loading && (
                <ArrowRight className="h-5 w-5" aria-hidden="true" />
              )}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link to="/login" className="link-underline font-bold">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
