import { useState, useEffect, useRef, useCallback } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { Flag, Check, X } from "lucide-react";
import { api, errorText, type User } from "./api";
import { Brand, Loading, type Notice } from "./ui";
import { Landing } from "./Landing";
import { AuthForm, ResetPassword } from "./Auth";
import { Workspace } from "./Workspace";
import { Profile } from "./Profile";
import { Admin } from "./Admin";
function App() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ text: string; bad: boolean } | null>(
    null,
  );
  const [light, setLight] = useState(
    () => localStorage.getItem("coffeenchat-theme") === "light",
  );
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const notice = useCallback<Notice>((text, bad = false) => {
    setToast({ text, bad });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 5000);
  }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    api<User>("/users/me", "GET", undefined, ctrl.signal)
      .then(setUser)
      .catch(() => {})
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, []);
  useEffect(() => {
    const channel = new BroadcastChannel("coffeenchat-session");
    const expired = () => {
      setUser(null);
      notice("Your session ended. Please sign in again.", true);
    };
    const crossTab = () => {
      api<User>("/users/me")
        .then(setUser)
        .catch(() => setUser(null));
    };
    channel.onmessage = crossTab;
    window.addEventListener("session-expired", expired);
    return () => {
      channel.close();
      window.removeEventListener("session-expired", expired);
    };
  }, [notice]);
  useEffect(() => {
    document.documentElement.dataset.theme = light ? "light" : "dark";
    localStorage.setItem("coffeenchat-theme", light ? "light" : "dark");
  }, [light]);
  const auth = (next: User | null) => {
    setUser(next);
    const c = new BroadcastChannel("coffeenchat-session");
    c.postMessage("changed");
    c.close();
  };
  const logout = async () => {
    try {
      await api("/users/logout", "POST");
      auth(null);
    } catch (e) {
      notice(errorText(e), true);
    }
  };
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing user={user} />} />
        <Route
          path="/login"
          element={
            loading ? (
              <Loading />
            ) : user ? (
              <Navigate to="/dashboard" />
            ) : (
              <AuthForm mode="login" auth={auth} notice={notice} />
            )
          }
        />
        <Route
          path="/signup"
          element={
            loading ? (
              <Loading />
            ) : user ? (
              <Navigate to="/dashboard" />
            ) : (
              <AuthForm mode="signup" auth={auth} notice={notice} />
            )
          }
        />
        <Route
          path="/reset-password"
          element={<ResetPassword notice={notice} />}
        />
        <Route
          path="/dashboard"
          element={
            loading ? (
              <Loading />
            ) : user ? (
              <Workspace
                key={user.id}
                user={user}
                logout={logout}
                notice={notice}
                theme={() => setLight(!light)}
                light={light}
              />
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/profile"
          element={
            loading ? (
              <Loading />
            ) : user ? (
              <Profile
                user={user}
                update={setUser}
                logout={logout}
                auth={auth}
                notice={notice}
              />
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin"
          element={
            loading ? (
              <Loading />
            ) : user?.is_admin ? (
              <Admin notice={notice} logout={logout} />
            ) : (
              <Navigate to="/dashboard" />
            )
          }
        />
        <Route
          path="*"
          element={
            <div className="empty-page">
              <Brand />
              <h1>This page is not here.</h1>
              <Link className="primary" to="/dashboard">
                Go to your workspace
              </Link>
            </div>
          }
        />
      </Routes>
      {toast && (
        <div className={"toast " + (toast.bad ? "bad" : "")} role="status">
          {toast.bad ? <Flag size={18} /> : <Check size={18} />}
          {toast.text}
          <button
            className="icon"
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}
    </BrowserRouter>
  );
}

export default App;
