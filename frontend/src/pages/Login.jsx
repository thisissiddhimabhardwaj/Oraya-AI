import AuthEditorial from "../components/AuthEditorial";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Logo } from "../components/Logo";
import { Button, Field } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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
    if (!email.trim()) next.email = "Enter your email address";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      next.email = "That doesn't look like a valid email";
    if (!password) next.password = "Enter your password";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    setFormError("");
    if (!validate()) return;
    setLoading(true);
    try {
      await login(email.trim(), password);
      navigate(location.state?.from || "/dashboard", { replace: true });
    } catch (err) {
      setFormError(err.message || "Could not sign you in");
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = () => {
    setEmail("demo@oraya.app");
    setPassword("oraya-demo-1");
    setErrors({});
    setFormError("");
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
          <h1 className="font-display text-3xl font-bold">Welcome back</h1>
          <p className="mt-1.5 text-sm text-muted">
            Pick up exactly where you left off.
          </p>

          {formError && (
            <div
              ref={summaryRef}
              tabIndex={-1}
              role="alert"
              aria-labelledby="login-error-title"
              className="mt-5 rounded-xl border border-danger/30 bg-[#fdecec] p-4"
            >
              <p
                id="login-error-title"
                className="text-sm font-bold text-danger"
              >
                There is a problem
              </p>
              <p className="mt-1 text-sm text-danger">{formError}</p>
            </div>
          )}

          <form onSubmit={submit} noValidate className="mt-6 space-y-4">
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
            <Field
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              error={errors.password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => validate()}
            />
            <Button
              type="submit"
              loading={loading}
              className="w-full"
              size="lg"
            >
              Log in
              {!loading && (
                <ArrowRight className="h-5 w-5" aria-hidden="true" />
              )}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-muted">
          New here?{" "}
          <Link to="/signup" className="link-underline font-bold">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
