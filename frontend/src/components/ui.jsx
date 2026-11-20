import { AlertCircle, Inbox, Loader2 } from "lucide-react";

export function Spinner({ className = "" }) {
  return (
    <Loader2
      className={`h-4 w-4 animate-spin ${className}`}
      aria-hidden="true"
    />
  );
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  className = "",
  children,
  ...rest
}) {
  const variantClass = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
    danger: "btn-primary bg-danger hover:bg-danger",
  }[variant];
  const sizeClass = size === "lg" ? "btn-lg" : "";
  return (
    <button
      type="button"
      className={`btn ${variantClass} ${sizeClass} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Chip({ selected = false, className = "", children, ...rest }) {
  return (
    <button
      type="button"
      className={`chip ${className}`}
      aria-pressed={selected}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", children, className = "" }) {
  const tones = {
    neutral: "bg-sunken text-muted border-line",
    coral: "bg-coral-soft text-coral-dark border-coral-soft",
    sage: "bg-sage-soft text-sage-ink border-sage-soft",
    info: "bg-[#eef0fd] text-info border-[#eef0fd]",
    danger: "bg-[#fdecec] text-danger border-[#fdecec]",
    warn: "bg-[#fbf1dd] text-warn border-[#fbf1dd]",
    ok: "bg-[#e6f2e9] text-ok border-[#e6f2e9]",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Field({ label, id, error, hint, className = "", ...rest }) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-ink">
          {label}
        </label>
      )}
      <input
        id={id}
        className="field"
        aria-invalid={error ? "true" : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        {...rest}
      />
      {hint && !error && (
        <p id={hintId} className="mt-1.5 text-sm text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p
          id={errorId}
          role="alert"
          className="mt-1.5 flex items-start gap-1.5 text-sm font-medium text-danger"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}

export function ProgressBar({ value, label }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label || "Progress"}
      className="h-2 w-full overflow-hidden rounded-full bg-sunken"
    >
      <div
        className="h-full rounded-full bg-coral transition-[width] duration-500 ease-[cubic-bezier(.2,.8,.3,1)]"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return (
    <div
      className="flex items-center justify-center gap-2 py-14 text-muted"
      role="status"
    >
      <Spinner className="h-5 w-5" />
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  title = "Something went wrong",
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#fdecec] text-danger">
        <AlertCircle className="h-5 w-5" aria-hidden="true" />
      </span>
      <div>
        <p className="font-bold text-ink">{title}</p>
        <p className="mx-auto mt-1 max-w-md text-sm text-muted">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, description, action, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-sunken text-muted">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <div>
        <p className="font-bold text-ink">{title}</p>
        {description && (
          <p className="mx-auto mt-1 max-w-md text-sm text-muted">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

/* -------------------------------------------------- minimal markdown renderer */
function renderInline(text, keyPrefix) {
  const parts = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_|[^*`_]+)/g;
  let match;
  let i = 0;
  while ((match = regex.exec(text)) !== null) {
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={`${keyPrefix}-${i}`}>{token.slice(2, -2)}</strong>,
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(
        <code
          key={`${keyPrefix}-${i}`}
          className="rounded border border-line bg-sunken px-1.5 py-0.5 text-[0.875em]"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (
      token.startsWith("_") &&
      token.endsWith("_") &&
      token.length > 2
    ) {
      parts.push(<em key={`${keyPrefix}-${i}`}>{token.slice(1, -1)}</em>);
    } else {
      parts.push(<span key={`${keyPrefix}-${i}`}>{token}</span>);
    }
    i += 1;
  }
  return parts;
}

export function Markdown({ text = "", className = "" }) {
  const lines = String(text).split("\n");
  const nodes = [];
  let listItems = [];
  let paragraph = [];

  const flushList = (key) => {
    if (listItems.length) {
      nodes.push(
        <ul key={`ul-${key}`}>
          {listItems.map((item, idx) => (
            <li key={idx}>{renderInline(item, `li-${key}-${idx}`)}</li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };
  const flushPara = (key) => {
    if (paragraph.length) {
      const content = paragraph.join(" ");
      nodes.push(<p key={`p-${key}`}>{renderInline(content, `p-${key}`)}</p>);
      paragraph = [];
    }
  };

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const trimmed = line.trim();
    if (!trimmed) {
      flushList(idx);
      flushPara(idx);
      return;
    }
    if (/^#{1,4}\s+/.test(trimmed)) {
      flushList(idx);
      flushPara(idx);
      const level = trimmed.match(/^#+/)[0].length;
      const content = trimmed.replace(/^#+\s+/, "");
      const Tag = ["h1", "h2", "h3", "h3"][level - 1] || "h3";
      nodes.push(
        <Tag key={`h-${idx}`}>{renderInline(content, `h-${idx}`)}</Tag>,
      );
      return;
    }
    if (/^[-*•]\s+/.test(trimmed)) {
      flushPara(idx);
      listItems.push(trimmed.replace(/^[-*•]\s+/, ""));
      return;
    }
    if (/^\d+\.\s+/.test(trimmed)) {
      flushPara(idx);
      listItems.push(trimmed.replace(/^\d+\.\s+/, ""));
      return;
    }
    flushList(idx);
    paragraph.push(trimmed);
  });
  flushList("last");
  flushPara("last");

  return <div className={`prose-oraya ${className}`}>{nodes}</div>;
}
