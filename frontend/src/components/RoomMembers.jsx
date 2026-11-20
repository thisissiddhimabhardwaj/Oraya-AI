import { useEffect, useState } from "react";
import { api } from "../lib/api";
export default function RoomMembers({ room, onChange }) {
  const [members, setMembers] = useState([]),
    [error, setError] = useState("");
  const load = () =>
    api
      .get(`/rooms/${room.id}/members`)
      .then((r) => setMembers(r.items))
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [room.id]);
  return (
    <section className="room-members">
      <h3>Learning together</h3>
      {members.map((m) => (
        <div key={m.user_id}>
          <span>
            {m.name} {m.is_owner ? "· Owner" : ""}
          </span>
          {room.is_owner && !m.is_owner && (
            <button
              onClick={async () => {
                if (!window.confirm(`Remove ${m.name} from this room?`)) return;
                try {
                  await api.del(`/rooms/${room.id}/members/${m.user_id}`);
                  await load();
                  onChange(await api.get(`/rooms/${room.id}`));
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              Remove
            </button>
          )}
        </div>
      ))}
      {room.is_owner && (
        <button
          className="room-rotate"
          onClick={async () => {
            try {
              onChange(await api.post(`/rooms/${room.id}/rotate-invite`, {}));
            } catch (e) {
              setError(e.message);
            }
          }}
        >
          Rotate invitation code
        </button>
      )}
      {error && <p role="status">{error}</p>}
    </section>
  );
}
