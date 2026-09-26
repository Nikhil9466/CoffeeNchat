import { useState, useEffect } from "react";
import { ArrowRight, Plus, Search, Check } from "lucide-react";
import { Avatar, Modal, type Notice } from "./ui";
import {
  api,
  errorText,
  type User,
  type Person,
  type Conversation,
} from "./api";
export function NewConversation({
  user,
  notice,
  close,
  created,
}: {
  user: User;
  notice: Notice;
  close: () => void;
  created: (c: Conversation) => void;
}) {
  const [group, setGroup] = useState(false),
    [people, setPeople] = useState<Person[]>([]),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [name, setName] = useState(""),
    [busy, setBusy] = useState(false),
    [hasMore, setHasMore] = useState(false),
    [offset, setOffset] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(
      () =>
        api<Person[]>(
          "/users?q=" + encodeURIComponent(query),
          "GET",
          undefined,
          ctrl.signal,
        )
          .then((rows) => {
            setOffset(rows.length);
            setPeople(rows.filter((p) => p.id !== user.id));
            setHasMore(rows.length === 50);
          })
          .catch((e) => {
            if (!ctrl.signal.aborted) notice(errorText(e), true);
          }),
      200,
    );
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [query, user.id, notice]);
  async function create(id?: string) {
    setBusy(true);
    try {
      created(
        await api<Conversation>(
          group ? "/conversations/group" : "/conversations",
          "POST",
          group
            ? { name, participant_ids: selected }
            : { is_group: false, participant_ids: [id] },
        ),
      );
    } catch (e) {
      notice(errorText(e), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Start something good" close={close}>
      <div className="segmented">
        <button
          className={!group ? "selected" : ""}
          onClick={() => setGroup(false)}
        >
          Direct message
        </button>
        <button
          className={group ? "selected" : ""}
          onClick={() => setGroup(true)}
        >
          New group
        </button>
      </div>
      {group && (
        <label>
          Group name
          <input
            value={name}
            maxLength={255}
            placeholder="Design team, weekend plans…"
            onChange={(e) => setName(e.target.value)}
          />
        </label>
      )}
      <div className="searchbox">
        <Search size={17} />
        <input
          value={query}
          placeholder="Search people by username"
          aria-label="Search people"
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="people-list">
        {people.map((p) => (
          <button
            disabled={busy}
            className="person-row"
            key={p.id}
            onClick={() =>
              group
                ? setSelected((s) =>
                    s.includes(p.id)
                      ? s.filter((x) => x !== p.id)
                      : [...s, p.id],
                  )
                : create(p.id)
            }
          >
            <Avatar name={p.username} />
            <span>
              <strong>{p.username}</strong>
              <small>{p.bio || "CoffeeNchat member"}</small>
            </span>
            {group ? (
              selected.includes(p.id) ? (
                <Check className="accent" />
              ) : (
                <Plus size={18} />
              )
            ) : (
              <ArrowRight size={17} />
            )}
          </button>
        ))}
        {!people.length && (
          <p className="muted">
            No people found. Invite someone to register on your CoffeeNchat
            instance.
          </p>
        )}
        {hasMore && (
          <button
            className="text-button"
            onClick={async () => {
              try {
                const rows = await api<Person[]>(
                  `/users?q=${encodeURIComponent(query)}&offset=${offset}`,
                );
                setPeople((prev) => [
                  ...prev,
                  ...rows.filter(
                    (p) => p.id !== user.id && !prev.some((x) => x.id === p.id),
                  ),
                ]);
                setOffset((prev) => prev + rows.length);
                setHasMore(rows.length === 50);
              } catch (e) {
                notice(errorText(e), true);
              }
            }}
          >
            Load more people
          </button>
        )}
      </div>
      {group && (
        <>
          <p className="muted small">
            Invitees can read existing group history. Only administrators can
            add or remove other members.
          </p>
          <button
            className="primary full"
            disabled={busy || !name.trim()}
            onClick={() => create()}
          >
            {busy
              ? "Creating…"
              : `Create group · ${selected.length + 1} members`}
          </button>
        </>
      )}
    </Modal>
  );
}
