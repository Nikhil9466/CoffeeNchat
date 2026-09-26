import { Link } from "react-router-dom";
import {
  ArrowRight,
  ShieldCheck,
  MessageCircle,
  Paperclip,
  Users,
} from "lucide-react";
import { Brand } from "./ui";
import type { User } from "./api";
export function Landing({ user }: { user: User | null }) {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <Brand />
        <div>
          <a href="#features">Features</a>
          <a href="#privacy">Privacy</a>
          <Link to="/login">Sign in</Link>
          <Link className="primary" to={user ? "/dashboard" : "/signup"}>
            {user ? "Open workspace" : "Get started"}
            <ArrowUpRight />
          </Link>
        </div>
      </nav>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">
            <span className="status-dot" /> YOUR PEOPLE. ONE PLACE.
          </span>
          <h1>
            Good conversations.
            <br />
            <span>Great connections.</span>
          </h1>
          <p>
            A little less noise. A lot more connection. Bring your people
            together in a thoughtful space for messages, ideas, and everything
            in between.
          </p>
          <div className="hero-actions">
            <Link className="primary" to={user ? "/dashboard" : "/signup"}>
              Find your conversation <ArrowRight size={18} />
            </Link>
            <a className="secondary" href="#features">
              Explore CoffeeNchat
            </a>
          </div>
          <div className="hero-note">
            <ShieldCheck size={16} /> Private conversations. A calmer workspace.
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-a" />
          <div className="orbit orbit-b" />
          <div className="orbit orbit-c" />
          <div className="orb-core">
            <MessageCircle size={60} />
          </div>
          <div className="floating-note">
            <span>✦</span> A space to connect
          </div>
        </div>
      </section>
      <section id="features" className="feature-section">
        <span className="eyebrow">BUILT FOR THE WAY YOU CONNECT</span>
        <h2>Small details. Better conversations.</h2>
        <div className="feature-grid">
          {[
            [
              MessageCircle,
              "Stay in the conversation",
              "Direct and group messages, with searchable history and automatic reconnection.",
            ],
            [
              Paperclip,
              "Keep ideas together",
              "Share files, save useful messages, and find what you need in one place.",
            ],
            [
              Users,
              "Make room for everyone",
              "Create a group, bring in your people, and manage members with clear roles.",
            ],
          ].map(([Icon, title, copy]) => {
            const I = Icon as typeof MessageCircle;
            return (
              <article key={String(title)}>
                <I size={25} />
                <h3>{String(title)}</h3>
                <p>{String(copy)}</p>
              </article>
            );
          })}
        </div>
      </section>
      <section id="privacy" className="privacy-card">
        <ShieldCheck size={34} />
        <div>
          <h2>Your workspace, with clear boundaries.</h2>
          <p>
            Messages and files are restricted to conversation members.
            Administrators can review reported messages. Manage your active
            sessions, report unwanted content, and stay in control. Messages are
            stored on the server; CoffeeNchat does not claim end-to-end encryption.
          </p>
        </div>
        <Link to="/signup" className="secondary">
          Create your account <ArrowRight size={16} />
        </Link>
      </section>
      <footer className="landing-footer">
        <Brand />
        <span>Made for meaningful conversations.</span>
        <span>© {new Date().getFullYear()} CoffeeNchat</span>
      </footer>
    </div>
  );
}
function ArrowUpRight() {
  return <ArrowRight size={15} style={{ transform: "rotate(-35deg)" }} />;
}
