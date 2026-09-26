import { useState, useEffect } from "react";
import { Download, FileText, MoreHorizontal, Plus, X } from "lucide-react";
import { Avatar, type Notice } from "./ui";
import {
  api,
  BASE,
  errorText,
  nameOf,
  type User,
  type Person,
  type Conversation,
  type FileItem,
} from "./api";
export function Details({
  conversation: c,
  user,
  notice,
  close,
  changed,
  left,
}: {
  conversation: Conversation;
  user: User;
  notice: Notice;
  close: () => void;
  changed: () => Promise<void>;
  left: () => void;
}) {
  const [tab, setTab] = useState("members"),
    [files, setFiles] = useState<FileItem[]>([]),
    [query, setQuery] = useState(""),
    [people, setPeople] = useState<Person[]>([]),
    [name, setName] = useState(c.name || ""),
    [busy, setBusy] = useState(false);
  const admin =
    c.participants.find((p) => p.user_id === user.id)?.role === "admin";
  useEffect(() => {
    api<FileItem[]>(`/conversations/${c.id}/files`)
      .then(setFiles)
      .catch((e) => notice(errorText(e), true));
  }, [c.id, notice]);
  async function action(
    path: string,
    method: string,
    body?: unknown,
    leave = false,
  ) {
    setBusy(true);
    try {
      await api(path, method, body);
      if (leave) left();
      else await changed();
      notice("Conversation updated");
    } catch (e) {
      notice(errorText(e), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <aside className="details-panel">
      <header>
        <h3>Conversation details</h3>
        <button className="icon" aria-label="Close details" onClick={close}>
          <X size={18} />
        </button>
      </header>
      <div className="details-identity">
        <Avatar name={nameOf(c, user.id)} group={c.is_group} />
        <h2>{nameOf(c, user.id)}</h2>
        <p>
          {c.is_group
            ? `${c.participants.length} people in this group`
            : "A conversation for two"}
        </p>
      </div>
      <div className="segmented">
        <button
          className={tab === "members" ? "selected" : ""}
          onClick={() => setTab("members")}
        >
          Members
        </button>
        <button
          className={tab === "files" ? "selected" : ""}
          onClick={() => setTab("files")}
        >
          Files
        </button>
      </div>
      {tab === "files" ? (
        <div className="detail-files">
          {files.map((f) => (
            <a href={BASE + f.url} key={f.id}>
              <FileText size={21} />
              <span>{f.filename}</span>
              <Download size={15} />
            </a>
          ))}
          {!files.length && <p className="muted">No files shared yet.</p>}
          {files.length > 0 && files.length % 50 === 0 && (
            <button
              className="text-button"
              onClick={() =>
                api<FileItem[]>(
                  `/conversations/${c.id}/files?offset=${files.length}`,
                )
                  .then((rows) => setFiles([...files, ...rows]))
                  .catch((e) => notice(errorText(e), true))
              }
            >
              Load more files
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="member-list">
            {c.participants.map((p) => (
              <div className="member" key={p.user_id}>
                <Avatar name={p.user?.username || "Former member"} />
                <div>
                  <strong>
                    {p.user?.username || "Former member"}
                    {p.user_id === user.id ? " (you)" : ""}
                  </strong>
                  <small>{c.is_group ? p.role : "Member"}</small>
                </div>
                {admin && p.user_id !== user.id && (
                  <details className="member-menu">
                    <summary aria-label={"Actions for " + p.user.username}>
                      <MoreHorizontal size={16} />
                    </summary>
                    <div>
                      {p.role !== "admin" && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            action(
                              `/conversations/${c.id}/participants/${p.user_id}/promote`,
                              "PATCH",
                            )
                          }
                        >
                          Make admin
                        </button>
                      )}
                      <button
                        disabled={busy}
                        onClick={() => {
                          if (window.confirm("Remove this member?"))
                            action(
                              `/conversations/${c.id}/participants/${p.user_id}`,
                              "DELETE",
                            );
                        }}
                      >
                        Remove member
                      </button>
                    </div>
                  </details>
                )}
              </div>
            ))}
          </div>
          {admin && (
            <div className="detail-controls">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  action("/conversations/" + c.id, "PATCH", { name });
                }}
              >
                <label>
                  Group name
                  <input
                    value={name}
                    maxLength={255}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <button
                  className="secondary full"
                  disabled={busy || !name.trim()}
                >
                  Save group name
                </button>
              </form>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    setPeople(
                      (
                        await api<Person[]>(
                          "/users?q=" + encodeURIComponent(query),
                        )
                      ).filter(
                        (p) => !c.participants.some((m) => m.user_id === p.id),
                      ),
                    );
                  } catch (err) {
                    notice(errorText(err), true);
                  }
                }}
              >
                <label>
                  Add a member
                  <input
                    value={query}
                    placeholder="Search username"
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
                <button className="secondary full">Search people</button>
              </form>
              {people.map((p) => (
                <button
                  className="person-row"
                  disabled={busy}
                  key={p.id}
                  onClick={async () => {
                    await action(
                      `/conversations/${c.id}/participants`,
                      "POST",
                      { user_id: p.id },
                    );
                    setPeople((prev) => prev.filter((x) => x.id !== p.id));
                  }}
                >
                  {p.username}
                  <Plus size={16} />
                </button>
              ))}
            </div>
          )}
          {c.is_group && (
            <div className="detail-controls">
              <button
                className="danger full"
                disabled={busy}
                onClick={() => {
                  if (
                    window.confirm(
                      "Leave this group? You will lose access to its messages.",
                    )
                  )
                    action(
                      `/conversations/${c.id}/participants/${user.id}`,
                      "DELETE",
                      undefined,
                      true,
                    );
                }}
              >
                Leave group
              </button>
              {admin && (
                <button
                  className="text-button danger-text full"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Delete this group and all its messages for everyone?",
                      )
                    )
                      action(
                        `/conversations/${c.id}`,
                        "DELETE",
                        undefined,
                        true,
                      );
                  }}
                >
                  Delete group permanently
                </button>
              )}
            </div>
          )}
        </>
      )}
    </aside>
  );
}
