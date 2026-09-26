import { useState, useEffect, useRef, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  MessageCircle,
  LoaderCircle,
} from "lucide-react";
import { Brand, Modal, type Notice } from "./ui";
import { api, errorText, type User } from "./api";
export function AuthForm({
  mode,
  auth,
  notice,
}: {
  mode: "login" | "signup";
  auth: (u: User) => void;
  notice: Notice;
}) {
  const signup = mode === "signup",
    navigate = useNavigate();
  const [busy, setBusy] = useState(false),
    [forgot, setForgot] = useState(false),
    [resetAvailable, setResetAvailable] = useState(false);
  useEffect(() => {
    api<{ password_reset: boolean }>("/auth/capabilities")
      .then((c) => setResetAvailable(c.password_reset))
      .catch(() => {});
  }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const u = await api<User>(
        signup ? "/users/register" : "/users/login",
        "POST",
        {
          email: data.get("email"),
          password: data.get("password"),
          ...(signup
            ? { username: data.get("username") }
            : { remember_me: data.get("remember") === "on" }),
        },
      );
      auth(u);
      navigate("/dashboard");
    } catch (err) {
      notice(errorText(err), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <Link className="back-link" to="/">
        <ArrowLeft size={17} /> Back to home
      </Link>
      <div className="auth-story">
        <Brand />
        <span className="eyebrow">A LITTLE CLOSER, EVERY DAY</span>
        <h1>
          Your next great
          <br />
          conversation
          <br />
          <em>starts here.</em>
        </h1>
        <p>
          A shared space for your team, your friends,
          <br />
          and the ideas that bring you together.
        </p>
        <div className="auth-decoration">
          <MessageCircle size={80} />
          <span>✦</span>
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">
          <span className="eyebrow">WELCOME TO COFFEENCHAT</span>
          <h2>{signup ? "Make yourself at home." : "Welcome back."}</h2>
          <p>
            {signup
              ? "Create an account and start connecting."
              : "Your conversations are waiting for you."}
          </p>
          <form onSubmit={submit}>
            {signup && (
              <label>
                Username
                <input
                  name="username"
                  minLength={3}
                  maxLength={50}
                  pattern="[A-Za-z0-9_ .\-]+"
                  autoComplete="username"
                  required
                  placeholder="What should we call you?"
                />
              </label>
            )}
            <label>
              Email address
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                placeholder="you@example.com"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                name="password"
                minLength={signup ? 10 : 1}
                maxLength={72}
                autoComplete={signup ? "new-password" : "current-password"}
                required
                placeholder={
                  signup ? "At least 10 characters" : "Enter your password"
                }
              />
            </label>
            {signup ? (
              <small>
                Use 10 or more characters (up to 72 UTF-8 bytes). Your email
                stays private.
              </small>
            ) : (
              <div className="form-between">
                <label className="checkbox">
                  <input type="checkbox" name="remember" /> Stay signed in for
                  30 days
                </label>
                {resetAvailable && (
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => setForgot(true)}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
            )}
            <button disabled={busy} className="primary full">
              {busy ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <>
                  {signup ? "Create account" : "Sign in"}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>
          <div className="auth-switch">
            {signup ? "Already part of the conversation?" : "New around here?"}{" "}
            <Link to={signup ? "/login" : "/signup"}>
              {signup ? "Sign in" : "Create an account"}
            </Link>
          </div>
          <p className="auth-privacy">
            <ShieldCheck size={14} /> Your messages are visible to conversation
            members. Group invitees can read existing group history.
          </p>
        </div>
      </div>
      {forgot && (
        <Modal title="Reset your password" close={() => setForgot(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const email = new FormData(e.currentTarget).get("email");
              setBusy(true);
              try {
                const r = await api<{ detail: string }>(
                  "/auth/forgot-password",
                  "POST",
                  { email },
                );
                notice(r.detail);
                setForgot(false);
              } catch (err) {
                notice(errorText(err), true);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Email
              <input type="email" name="email" required />
            </label>
            <button disabled={busy} className="primary full">
              Send reset link
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
export function ResetPassword({ notice }: { notice: Notice }) {
  const [busy, setBusy] = useState(false);
  const token = useRef(window.location.hash.slice(1));
  const navigate = useNavigate();
  useEffect(() => {
    history.replaceState(null, "", window.location.pathname);
  }, []);
  return (
    <div className="empty-page">
      <Brand />
      <div className="standalone-card">
        <h1>Choose a new password</h1>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              await api("/auth/reset-password", "POST", {
                token: token.current,
                password: new FormData(e.currentTarget).get("password"),
              });
              notice("Password updated. Sign in to continue.");
              navigate("/login");
            } catch (err) {
              notice(errorText(err), true);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            New password
            <input
              name="password"
              type="password"
              minLength={10}
              maxLength={72}
              required
            />
          </label>
          <button className="primary" disabled={busy}>
            Update password
          </button>
        </form>
      </div>
    </div>
  );
}
