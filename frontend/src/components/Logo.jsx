export function Logo({ size = "md", showWordmark = true }) {
  const text =
    size === "lg" ? "text-4xl" : size === "sm" ? "text-xl" : "text-2xl";
  return (
    <span className="inline-flex items-baseline gap-1.5 select-none">
      <span
        className={`font-display font-extrabold tracking-tight text-ink ${text}`}
      >
        Oraya
      </span>
      {showWordmark && (
        <svg
          width="14"
          height="16"
          viewBox="0 0 14 16"
          aria-hidden="true"
          className="translate-y-[-6px]"
        >
          <path
            d="M2 9 L1 15"
            stroke="#E8705B"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          <path
            d="M7 6 L7 12"
            stroke="#E8705B"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          <path
            d="M12 3 L14 8"
            stroke="#E8705B"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
        </svg>
      )}
      <span className="sr-only">ORAYA</span>
    </span>
  );
}
