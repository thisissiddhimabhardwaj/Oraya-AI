export function fmtTs(seconds = 0) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600),
    m = Math.floor((s % 3600) / 60),
    r = s % 60;
  return h
    ? `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`
    : `${m}:${String(r).padStart(2, "0")}`;
}

/** "1:35" | "95" | "1:02:03" -> seconds, or null when unparseable/empty. */
export function parseTs(text) {
  const t = String(text || "").trim();
  if (!t) return null;
  if (!/^\d+(:\d{1,2}){0,2}$/.test(t)) return NaN;
  const parts = t.split(":").map(Number);
  if (parts.slice(1).some((n) => n >= 60)) return NaN;
  return parts.reduce((a, n) => a * 60 + n, 0);
}

export const lectureLink = (id, seconds) =>
  `/lecture/${id}${seconds > 0 ? `?t=${Math.floor(seconds)}` : ""}`;
