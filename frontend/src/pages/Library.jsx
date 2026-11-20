import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookOpen, Plus, Search, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Loading,
} from "../components/ui";
import { api } from "../lib/api";

function timeAgo(iso) {
  const then = new Date(iso);
  const days = Math.floor((Date.now() - then.getTime()) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function Library() {
  const navigate = useNavigate();
  const [lectures, setLectures] = useState([]);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/lectures");
      setLectures(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const scoped = sourceFilter
      ? lectures.filter((l) =>
          sourceFilter === "document"
            ? l.source === "document"
            : l.source !== "document",
        )
      : lectures;
    if (!q) return scoped;
    return scoped.filter(
      (l) =>
        l.title.toLowerCase().includes(q) ||
        (l.channel || "").toLowerCase().includes(q),
    );
  }, [lectures, query, sourceFilter]);

  const remove = async (id) => {
    if (
      !window.confirm("Delete this lecture and everything generated from it?")
    )
      return;
    setDeletingId(id);
    try {
      await api.del(`/lectures/${id}`);
      setLectures((prev) => prev.filter((l) => l.id !== id));
    } catch (err) {
      window.alert(err.message || "Couldn't delete that lecture");
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) return <Loading label="Loading your library…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">Library</span>
          <h1 className="mt-1 font-display text-3xl font-extrabold sm:text-4xl">
            A library of possibilities.
          </h1>
        </div>
        <Button onClick={() => navigate("/learn/new")}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          New lecture
        </Button>
      </div>

      <div className="flex gap-2" role="group" aria-label="Material type">
        {[
          ["", "All materials"],
          ["video", "Lectures"],
          ["document", "Documents"],
        ].map(([v, t]) => (
          <button
            key={v}
            className={`btn btn-secondary ${sourceFilter === v ? "!bg-sage-soft" : ""}`}
            aria-pressed={sourceFilter === v}
            onClick={() => setSourceFilter(v)}
          >
            {t}
          </button>
        ))}
      </div>
      {lectures.length > 0 && (
        <div className="relative max-w-md">
          <Search
            className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <label htmlFor="library-search" className="sr-only">
            Search lectures
          </label>
          <input
            id="library-search"
            type="search"
            className="field pl-10"
            placeholder="Search by title or channel…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      )}

      {lectures.length === 0 ? (
        <div className="card">
          <EmptyState
            title="Your library is empty"
            description="Add a lecture or document. Your questions, notes and practice will grow from here."
            icon={BookOpen}
            action={
              <Button onClick={() => navigate("/learn/new")}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                Add your first lecture
              </Button>
            }
          />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No matches"
            description={`Nothing in your library matches “${query}”.`}
            action={
              <Button variant="secondary" onClick={() => setQuery("")}>
                Clear search
              </Button>
            }
          />
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((lec) => (
            <li
              key={lec.id}
              className="card card-hover flex flex-col overflow-hidden"
            >
              <button
                type="button"
                onClick={() => navigate(`/lecture/${lec.id}`)}
                className="block text-left"
              >
                <div className="aspect-video w-full overflow-hidden bg-sunken">
                  {lec.thumbnail ? (
                    <img
                      src={lec.thumbnail}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="grid h-full w-full place-items-center text-muted">
                      <BookOpen className="h-7 w-7" aria-hidden="true" />
                    </div>
                  )}
                </div>
                <div className="flex flex-1 flex-col p-4">
                  <p className="line-clamp-2 text-sm font-bold leading-snug">
                    {lec.title}
                  </p>
                  <p className="mt-1 truncate text-xs text-muted">
                    {lec.channel || "Unknown channel"} ·{" "}
                    {timeAgo(lec.created_at)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {lec.source === "sample" && (
                      <Badge tone="sage">Sample</Badge>
                    )}
                    {lec.transcript_status === "ready" ? (
                      <Badge tone="neutral">Transcript ready</Badge>
                    ) : (
                      <Badge tone="warn">No transcript</Badge>
                    )}
                  </div>
                </div>
              </button>

              <div className="mt-auto flex items-center justify-between border-t border-line px-4 py-3">
                <Link
                  to={`/lecture/${lec.id}`}
                  className="link-underline text-sm font-bold"
                >
                  Open workspace
                </Link>
                <button
                  className="text-xs text-forest underline"
                  type="button"
                  aria-label={`Rename ${lec.title}`}
                  onClick={async () => {
                    const title = window.prompt("Material title", lec.title);
                    if (!title?.trim()) return;
                    try {
                      await api.patch(`/lectures/${lec.id}`, {
                        title: title.trim(),
                      });
                      setLectures((rows) =>
                        rows.map((r) =>
                          r.id === lec.id ? { ...r, title: title.trim() } : r,
                        ),
                      );
                    } catch (e) {
                      window.alert(e.message);
                    }
                  }}
                >
                  Rename
                </button>
                <button
                  type="button"
                  onClick={() => remove(lec.id)}
                  disabled={deletingId === lec.id}
                  aria-label={`Delete ${lec.title}`}
                  className="flex h-9 w-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-[#fdecec] hover:text-danger disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
