import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Flag,
  LogOut,
  MessageCircle,
  Search,
  Send,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Brand, type Notice } from "./ui";
import { api, errorText, type User } from "./api";
interface AdminUser extends User {
  is_disabled: boolean;
}
interface Report {
  id: string;
  reason: string;
  content: string;
  created_at: string;
}
export function Admin({
  notice,
  logout,
}: {
  notice: Notice;
  logout: () => Promise<void>;
}) {
  const [stats, setStats] = useState<Record<string, number>>({}),
    [users, setUsers] = useState<AdminUser[]>([]),
    [reports, setReports] = useState<Report[]>([]),
    [search, setSearch] = useState(""),
    [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [s, u, r] = await Promise.all([
      api<Record<string, number>>("/admin/stats"),
      api<AdminUser[]>("/admin/users"),
      api<Report[]>("/admin/reports"),
    ]);
    setStats(s);
    setUsers(u);
    setReports(r);
  }, []);
  // Initial remote-data synchronization; no derived state is computed here.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load().catch((e) => notice(errorText(e), true));
  }, [load, notice]);
  async function resolve(id: string, action: string) {
    setBusy(true);
    try {
      await api(`/admin/reports/${id}/resolve`, "POST", { action });
      await load();
      notice(
        action === "delete" ? "Reported message removed" : "Report dismissed",
      );
    } catch (e) {
      notice(errorText(e), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="admin-page">
      <nav>
        <Brand />
        <div>
          <Link className="secondary" to="/dashboard">
            <ArrowLeft size={16} /> Messages
          </Link>
          <button className="secondary" onClick={logout}>
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </nav>
      <header className="page-title">
        <span className="eyebrow">WORKSPACE ADMINISTRATION</span>
        <h1>A healthier place to connect.</h1>
        <p>Real activity. Clear decisions. A community worth looking after.</p>
      </header>
      <div className="stats-grid">
        {[
          ["total_users", "Registered users", Users],
          ["active_rooms", "Conversations", MessageCircle],
          ["messages_today", "Messages · last 24h", Send],
          ["reported_content", "Open reports", Flag],
          ["active_sessions", "Valid sessions", ShieldCheck],
        ].map(([key, label, Icon]) => {
          const I = Icon as typeof Users;
          return (
            <article key={String(key)}>
              <I size={22} />
              <span>{String(label)}</span>
              <strong>{stats[String(key)]?.toLocaleString() ?? "—"}</strong>
            </article>
          );
        })}
      </div>
      <section className="settings-card">
        <div className="section-heading">
          <h2>User directory</h2>
          <form
            className="searchbox"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                setUsers(
                  await api<AdminUser[]>(
                    "/admin/users?q=" + encodeURIComponent(search),
                  ),
                );
              } catch (err) {
                notice(errorText(err), true);
              }
            }}
          >
            <Search size={16} />
            <input
              aria-label="Search users"
              placeholder="Search username, then Enter"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </form>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.username}</strong>
                    <small>{u.email}</small>
                  </td>
                  <td>{u.is_admin ? "Administrator" : "Member"}</td>
                  <td>
                    <span
                      className={"badge " + (u.is_disabled ? "suspended" : "")}
                    >
                      {u.is_disabled ? "Suspended" : "Enabled"}
                    </span>
                  </td>
                  <td>
                    {!u.is_admin && (
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={async () => {
                          if (
                            !window.confirm(
                              `${u.is_disabled ? "Restore" : "Suspend"} ${u.username}?`,
                            )
                          )
                            return;
                          setBusy(true);
                          try {
                            await api("/admin/users/" + u.id, "PATCH", {
                              disabled: !u.is_disabled,
                            });
                            await load();
                            notice("Account updated");
                          } catch (e) {
                            notice(errorText(e), true);
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        {u.is_disabled ? "Restore access" : "Suspend"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {users.length > 0 && users.length % 50 === 0 && (
          <button
            className="text-button"
            onClick={() =>
              api<AdminUser[]>(
                `/admin/users?q=${encodeURIComponent(search)}&offset=${users.length}`,
              )
                .then((rows) => setUsers([...users, ...rows]))
                .catch((e) => notice(errorText(e), true))
            }
          >
            Load more users
          </button>
        )}
      </section>
      <section className="settings-card">
        <div className="section-heading">
          <h2>Reports requiring attention</h2>
          <button
            className="text-button"
            onClick={() => load().catch((e) => notice(errorText(e), true))}
          >
            Refresh
          </button>
        </div>
        {!reports.length ? (
          <div className="report-empty">
            <ShieldCheck size={30} />
            <h3>All clear.</h3>
            <p>No open reports to review.</p>
          </div>
        ) : (
          reports.map((r) => (
            <article className="report" key={r.id}>
              <div>
                <span className="badge">Reported message</span>
                <blockquote>{r.content || "Attachment message"}</blockquote>
                <p>{r.reason}</p>
                <small>{new Date(r.created_at).toLocaleString()}</small>
              </div>
              <div>
                <button
                  disabled={busy}
                  className="secondary"
                  onClick={() => resolve(r.id, "dismiss")}
                >
                  Dismiss
                </button>
                <button
                  disabled={busy}
                  className="danger"
                  onClick={() => {
                    if (
                      window.confirm(
                        "Remove the reported message for everyone?",
                      )
                    )
                      resolve(r.id, "delete");
                  }}
                >
                  Remove message
                </button>
              </div>
            </article>
          ))
        )}
        {reports.length > 0 && reports.length % 50 === 0 && (
          <button
            className="text-button"
            onClick={() =>
              api<Report[]>(`/admin/reports?offset=${reports.length}`)
                .then((rows) =>
                  setReports((prev) => [
                    ...prev,
                    ...rows.filter((r) => !prev.some((p) => p.id === r.id)),
                  ]),
                )
                .catch((e) => notice(errorText(e), true))
            }
          >
            Load more reports
          </button>
        )}
      </section>
    </div>
  );
}
