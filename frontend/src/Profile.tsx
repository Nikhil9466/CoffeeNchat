import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, LogOut, ShieldCheck } from "lucide-react";
import { Avatar, Brand, Modal, type Notice } from "./ui";
import { api, errorText, type User, type Session } from "./api";
export function Profile({
  user,
  update,
  logout,
  auth,
  notice,
}: {
  user: User;
  update: (u: User) => void;
  logout: () => Promise<void>;
  auth: (u: User | null) => void;
  notice: Notice;
}) {
  const [sessions, setSessions] = useState<Session[]>([]),
    [busy, setBusy] = useState(false),
    [deleting, setDeleting] = useState(false);
  const load = useCallback(
    () =>
      api<Session[]>("/users/sessions")
        .then(setSessions)
        .catch((e) => notice(errorText(e), true)),
    [notice],
  );
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="settings-page">
      <nav>
        <Brand />
        <Link className="secondary" to="/dashboard">
          <ArrowLeft size={16} /> Back to messages
        </Link>
      </nav>
      <header className="page-title">
        <span className="eyebrow">MAKE IT YOURS</span>
        <h1>Profile & settings</h1>
        <p>Your identity, your preferences, your peace of mind.</p>
      </header>
      <div className="settings-grid">
        <section className="settings-card">
          <div className="profile-identity">
            <Avatar name={user.username} />
            <div>
              <h2>{user.username}</h2>
              <p>{user.email}</p>
            </div>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              const form = new FormData(e.currentTarget);
              try {
                update(
                  await api<User>("/users/" + user.id, "PUT", {
                    username: form.get("username"),
                    bio: form.get("bio"),
                  }),
                );
                notice("Profile updated");
              } catch (err) {
                notice(errorText(err), true);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Username
              <input
                name="username"
                defaultValue={user.username}
                minLength={3}
                maxLength={50}
                required
              />
            </label>
            <label>
              A little about you
              <textarea
                name="bio"
                defaultValue={user.bio}
                maxLength={240}
                placeholder="What brings you here?"
                rows={3}
              />
            </label>
            <button disabled={busy} className="primary">
              Save profile <Check size={17} />
            </button>
          </form>
          <hr />
          <h3>Notifications</h3>
          <p className="muted">
            Receive a private notification when a message arrives while this
            browser tab is in the background. Message text stays hidden.
          </p>
          <button
            className="secondary"
            onClick={async () => {
              if (!("Notification" in window)) {
                notice("Browser notifications are unavailable here.", true);
                return;
              }
              const permission = await Notification.requestPermission();
              notice(
                permission === "granted"
                  ? "Notifications enabled."
                  : "Notifications are blocked. You can change this in browser settings.",
                permission !== "granted",
              );
            }}
          >
            Enable browser notifications
          </button>
        </section>
        <section className="settings-card">
          <h2>Connected sessions</h2>
          <p className="muted">Sign out a device you no longer use.</p>
          <div className="sessions">
            {sessions.map((s) => (
              <div key={s.id}>
                <ShieldCheck size={20} />
                <span>
                  <strong>
                    {s.current ? "This browser" : s.label.slice(0, 55)}
                  </strong>
                  <small>
                    Signed in {new Date(s.created_at).toLocaleString()}
                  </small>
                  <small>
                    Expires {new Date(s.expires_at).toLocaleString()}
                  </small>
                </span>
                {!s.current && (
                  <button
                    className="icon"
                    aria-label="End session"
                    onClick={async () => {
                      try {
                        await api("/users/sessions/" + s.id, "DELETE");
                        await load();
                        notice("Session signed out");
                      } catch (e) {
                        notice(errorText(e), true);
                      }
                    }}
                  >
                    <LogOut size={17} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <button className="secondary" onClick={logout}>
            <LogOut size={16} /> Sign out of this browser
          </button>
        </section>
        <section className="settings-card">
          <h2>Change password</h2>
          <p className="muted">
            Changing your password signs out every session.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              const form = new FormData(e.currentTarget);
              try {
                await api("/users/password", "POST", {
                  current_password: form.get("current_password"),
                  password: form.get("password"),
                });
                auth(null);
                notice("Password changed. Sign in again.");
              } catch (err) {
                notice(errorText(err), true);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Current password
              <input
                type="password"
                name="current_password"
                autoComplete="current-password"
                required
              />
            </label>
            <label>
              New password
              <input
                type="password"
                name="password"
                autoComplete="new-password"
                minLength={10}
                maxLength={72}
                required
              />
            </label>
            <button disabled={busy} className="secondary">
              Update password
            </button>
          </form>
        </section>
        <section className="settings-card danger-card">
          <h2>Delete account</h2>
          <p>
            Your profile and sessions will be removed. Messages already shared
            remain in conversations with your identity removed. Transfer group
            administration before deleting your account.
          </p>
          <button className="danger" onClick={() => setDeleting(true)}>
            Delete my account
          </button>
        </section>
      </div>
      {deleting && (
        <Modal title="Delete your account?" close={() => setDeleting(false)}>
          <p className="muted">
            This cannot be undone. Shared messages remain as history with no
            linked sender.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api("/users/" + user.id, "DELETE", {
                  current_password: new FormData(e.currentTarget).get(
                    "password",
                  ),
                });
                auth(null);
                notice("Account deleted");
              } catch (err) {
                notice(errorText(err), true);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Confirm your password
              <input name="password" type="password" required />
            </label>
            <button className="danger full" disabled={busy}>
              Permanently delete account
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
