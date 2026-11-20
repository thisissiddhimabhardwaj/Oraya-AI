import RoomMembers from "../components/RoomMembers";
import { useAuth } from "../context/AuthContext";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, ErrorState } from "../components/ui";
import { Users, Plus, ArrowLeft } from "lucide-react";
export default function StudyRooms() {
  const { user } = useAuth();
  const [rooms, setRooms] = useState([]),
    [room, setRoom] = useState(null),
    [error, setError] = useState(""),
    [name, setName] = useState(""),
    [code, setCode] = useState(""),
    [content, setContent] = useState(""),
    [kind, setKind] = useState("note"),
    [busy, setBusy] = useState(false),
    [revealed, setRevealed] = useState({});
  const load = () =>
    api
      .get("/rooms")
      .then((r) => setRooms(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (!room) return;
    const id = setInterval(
      () =>
        api
          .get(`/rooms/${room.id}`)
          .then(setRoom)
          .catch((e) => setError(e.message)),
      5000,
    );
    return () => clearInterval(id);
  }, [room?.id]);
  const run = async (fn) => {
    setError("");
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="studio-page">
      <header className="studio-heading">
        <p className="eyebrow">EXPLORE · BETTER TOGETHER</p>
        <h1>Good questions travel further.</h1>
        <p>
          A shared place for notes, goals, and practice. Updates arrive every
          five seconds.
        </p>
      </header>
      {error && <ErrorState message={error} />}
      {!room ? (
        <>
          <div className="studio-split">
            <form
              className="studio-paper"
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  setRoom(await api.post("/rooms", { name }));
                  setName("");
                });
              }}
            >
              <h2>Gather your people.</h2>
              <label className="studio-label">
                Room name
                <input
                  required
                  className="field"
                  minLength={2}
                  maxLength={120}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <Button type="submit" disabled={busy}>
                <Plus size={16} />
                Create room
              </Button>
            </form>
            <form
              className="studio-aside"
              onSubmit={(e) => {
                e.preventDefault();
                run(async () =>
                  setRoom(await api.post("/rooms/join", { code: code.trim() })),
                );
              }}
            >
              <h2>Have an invitation?</h2>
              <label className="studio-label">
                Invite code
                <input
                  required
                  className="field"
                  minLength={12}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </label>
              <Button type="submit" variant="secondary" disabled={busy}>
                Join room <Users size={16} />
              </Button>
            </form>
          </div>
          <section className="studio-room-list">
            {rooms.map((r) => (
              <button
                key={r.id}
                onClick={() =>
                  run(async () => setRoom(await api.get(`/rooms/${r.id}`)))
                }
              >
                <Users size={25} />
                <h2>{r.name}</h2>
                <p>
                  {r.member_count} members{" "}
                  {r.is_owner ? "· You own this room" : ""}
                </p>
                <span>Open room →</span>
              </button>
            ))}
          </section>
        </>
      ) : (
        <>
          <div className="studio-bottom">
            <Button variant="secondary" onClick={() => setRoom(null)}>
              <ArrowLeft size={16} />
              All rooms
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    room.is_owner
                      ? "Delete this room and all shared entries?"
                      : "Leave this room?",
                  )
                )
                  run(async () => {
                    if (room.is_owner) await api.del(`/rooms/${room.id}`);
                    else await api.post(`/rooms/${room.id}/leave`, {});
                    setRoom(null);
                  });
              }}
            >
              {room.is_owner ? "Delete room" : "Leave room"}
            </Button>
          </div>
          <div className="studio-split">
            <section className="studio-paper">
              <p className="eyebrow">{room.member_count} MEMBERS</p>
              <h2>{room.name}</h2>
              <p className="studio-notice">
                Invite someone by sharing this code:{" "}
                <code className="select-all break-all">{room.invite_code}</code>
                . Anyone holding it can join.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    setRoom(
                      await api.post(`/rooms/${room.id}/entries`, {
                        kind,
                        content,
                      }),
                    );
                    setContent("");
                  });
                }}
              >
                <label className="studio-label">
                  Share
                  <select
                    className="field"
                    value={kind}
                    onChange={(e) => setKind(e.target.value)}
                  >
                    <option value="note">A note</option>
                    <option value="goal">A goal</option>
                    <option value="quiz">A saved quiz</option>
                  </select>
                </label>
                <label className="studio-label">
                  {kind === "quiz"
                    ? "Saved quiz ID (from the lecture quiz panel)"
                    : "Your contribution"}
                  <textarea
                    required
                    maxLength={10000}
                    className="field"
                    rows={4}
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                  />
                </label>
                <Button type="submit" disabled={busy}>
                  Share with room
                </Button>
              </form>
            </section>
            <aside className="studio-aside">
              <RoomMembers room={room} onChange={setRoom} />
              <h2>One goal. Many perspectives.</h2>
              <p>
                Everyone can contribute. Authors and the room owner can edit
                contributions. Your private learning library stays private.
              </p>
            </aside>
          </div>
          <section className="studio-feed">
            <h2>Shared activity</h2>
            {room.entries.length === 0 ? (
              <p>Your first shared idea starts here.</p>
            ) : (
              room.entries
                .slice()
                .reverse()
                .map((e) => (
                  <article key={e.id}>
                    <div className="studio-entry-meta">
                      {e.author} · {e.kind} ·{" "}
                      {new Date(e.created_at).toLocaleString()}
                    </div>
                    {e.kind === "quiz" ? (
                      <div>
                        {(() => {
                          try {
                            const q = JSON.parse(e.content);
                            return (
                              <>
                                <h3>{q.title}</h3>
                                {q.questions.map((x, i) => (
                                  <div key={i}>
                                    <p>
                                      {i + 1}. {x.prompt}
                                    </p>
                                    <ul>
                                      {x.options?.map((o) => (
                                        <li key={o}>{o}</li>
                                      ))}
                                    </ul>
                                    {revealed[`${e.id}-${i}`] ? (
                                      <p>
                                        <b>{x.answer}</b> · {x.explanation}
                                      </p>
                                    ) : (
                                      <button
                                        className="text-forest underline"
                                        onClick={() =>
                                          setRevealed({
                                            ...revealed,
                                            [`${e.id}-${i}`]: true,
                                          })
                                        }
                                      >
                                        Reveal answer
                                      </button>
                                    )}
                                  </div>
                                ))}
                              </>
                            );
                          } catch {
                            return "Unable to display this quiz.";
                          }
                        })()}
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{e.content}</p>
                    )}
                    {e.kind !== "quiz" &&
                      (e.user_id === user.id || room.is_owner) && (
                        <button
                          className="text-xs text-forest underline mt-3"
                          disabled={busy}
                          onClick={() => {
                            const content = window.prompt(
                              "Edit shared contribution",
                              e.content,
                            );
                            if (!content?.trim()) return;
                            run(async () =>
                              setRoom(
                                await api.patch(
                                  `/rooms/${room.id}/entries/${e.id}`,
                                  { content },
                                ),
                              ),
                            );
                          }}
                        >
                          Edit contribution
                        </button>
                      )}
                    {e.kind === "goal" && (
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() =>
                          run(async () =>
                            setRoom(
                              await api.patch(
                                `/rooms/${room.id}/entries/${e.id}`,
                                { completed: !e.completed },
                              ),
                            ),
                          )
                        }
                      >
                        {e.completed
                          ? "✓ Completed · Reopen"
                          : "Mark goal complete"}
                      </Button>
                    )}
                  </article>
                ))
            )}
          </section>
        </>
      )}
    </div>
  );
}
