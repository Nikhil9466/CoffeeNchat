import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  CheckCheck,
  ChevronDown,
  Download,
  FileText,
  Flag,
  LoaderCircle,
  LogOut,
  Menu,
  MessageCircle,
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Star,
  Trash2,
  Users,
  Wifi,
  WifiOff,
  X,
  Moon,
  Sun,
} from "lucide-react";
import { Brand, Avatar, Loading, Modal, type Notice } from "./ui";
import {
  api,
  BASE,
  errorText,
  nameOf,
  socketUrl,
  timeOf,
  type Conversation,
  type Message,
  type Summary,
  type User,
} from "./api";
import { NewConversation } from "./NewConversation";
import { Details } from "./Details";
export function Workspace({
  user,
  logout,
  notice,
  theme,
  light,
}: {
  user: User;
  logout: () => Promise<void>;
  notice: Notice;
  theme: () => void;
  light: boolean;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]),
    [summaries, setSummaries] = useState<Record<string, Summary>>({}),
    [active, setActive] = useState(""),
    [messages, setMessages] = useState<Record<string, Message[]>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({}),
    [search, setSearch] = useState(""),
    [messageSearch, setMessageSearch] = useState(""),
    [results, setResults] = useState<Message[] | null>(null);
  const [connection, setConnection] = useState("connecting"),
    [mobile, setMobile] = useState(false),
    [details, setDetails] = useState(false),
    [newChat, setNewChat] = useState(false),
    [saved, setSaved] = useState<Message[] | null>(null);
  const [sending, setSending] = useState(false),
    [loading, setLoading] = useState(false),
    [more, setMore] = useState<Record<string, boolean>>({}),
    [typing, setTyping] = useState<Record<string, number>>({}),
    [listMore, setListMore] = useState(false);
  const [report, setReport] = useState<Message | null>(null),
    [pending, setPending] = useState<
      Record<string, { content: string; client_id: string; media_url?: string }>
    >({});
  const socket = useRef<WebSocket | null>(null),
    activeRef = useRef(active),
    end = useRef<HTMLDivElement>(null),
    file = useRef<HTMLInputElement>(null),
    lastType = useRef(0),
    busySend = useRef(false),
    listVersion = useRef(0),
    separateView = useRef(false),
    known = useRef(messages),
    epoch = useRef(0);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setMobile(true);
        requestAnimationFrame(() =>
          document.getElementById("conversation-search")?.focus(),
        );
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    separateView.current = saved !== null || results !== null;
  }, [saved, results]);
  const current = conversations.find((c) => c.id === active),
    title = current ? nameOf(current, user.id) : "Your conversations";
  useEffect(() => {
    activeRef.current = active;
  }, [active]);
  useEffect(() => {
    known.current = messages;
  }, [messages]);
  const merge = useCallback(
    (cid: string, items: Message[]) =>
      setMessages((prev) => {
        const map = new Map((prev[cid] || []).map((m) => [m.id, m]));
        items.forEach((m) => map.set(m.id, m));
        return {
          ...prev,
          [cid]: Array.from(map.values()).sort(
            (a, b) =>
              a.created_at.localeCompare(b.created_at) ||
              a.id.localeCompare(b.id),
          ),
        };
      }),
    [],
  );
  const loadList = useCallback(async (offset = 0) => {
    const version = ++listVersion.current;
    const [cs, ss] = await Promise.all([
      api<Conversation[]>("/conversations?limit=50&offset=" + offset),
      api<Summary[]>("/inbox?limit=50&offset=" + offset),
    ]);
    if (version !== listVersion.current) return;
    setConversations((prev) =>
      offset
        ? [...prev, ...cs.filter((c) => !prev.some((x) => x.id === c.id))]
        : [...cs, ...prev.filter((c) => !cs.some((x) => x.id === c.id))],
    );
    setSummaries((prev) => ({
      ...prev,
      ...Object.fromEntries(ss.map((s) => [s.id, s])),
    }));
    setListMore(cs.length === 50);
  }, []);
  const refresh = useCallback(
    async (cid: string, catchup = false) => {
      const existing = new Set((known.current[cid] || []).map((m) => m.id));
      let before = "";
      let page: Message[];
      let rounds = 0;
      let latest: Message | undefined;
      do {
        page = await api<Message[]>(
          `/conversations/${cid}/messages?limit=50${before ? "&before=" + before : ""}`,
        );
        if (!before) latest = page.at(-1);
        merge(cid, page);
        if (!before)
          setMore((prev) => ({ ...prev, [cid]: page.length === 50 }));
        if (!catchup || !existing.size || page.some((m) => existing.has(m.id)))
          break;
        before = page[0]?.id || "";
        rounds++;
      } while (page.length === 50 && rounds < 100);
      return latest;
    },
    [merge],
  );
  // Initial remote-data synchronization; no derived state is computed here.
  useEffect(() => {
    loadList().catch((e) => notice(errorText(e), true));
  }, [loadList, notice]);
  useEffect(() => {
    let disposed = false,
      timer: ReturnType<typeof setTimeout>,
      attempt = 0;
    const connect = () => {
      if (disposed) return;
      setConnection("connecting");
      const ws = new WebSocket(socketUrl());
      socket.current = ws;
      ws.onopen = () => {
        attempt = 0;
        setConnection("connected");
        loadList().catch(() => {});
        if (activeRef.current)
          refresh(activeRef.current, true).catch((e) =>
            notice(errorText(e), true),
          );
      };
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "message" && data.message?.id) {
            const m = data.message as Message;
            merge(m.conversation_id, [m]);
            loadList().catch(() => {});
            if (
              m.conversation_id === activeRef.current &&
              document.visibilityState === "visible" &&
              !separateView.current
            ) {
              api(`/conversations/${m.conversation_id}/read`, "POST", {
                last_message_id: m.id,
              }).catch(() => {});
              end.current?.scrollIntoView({ behavior: "smooth" });
            } else if (
              m.sender_id !== user.id &&
              document.visibilityState === "hidden" &&
              "Notification" in window &&
              Notification.permission === "granted"
            ) {
              new Notification("New message on CoffeeNchat", {
                body: "Open your workspace to read it.",
              });
            }
          } else if (data.type === "typing" && data.user_id !== user.id)
            setTyping((prev) => ({
              ...prev,
              [data.conversation_id]: Date.now(),
            }));
          else if (data.type === "read")
            setConversations((prev) =>
              prev.map((c) =>
                c.id === data.conversation_id
                  ? {
                      ...c,
                      participants: c.participants.map((p) =>
                        p.user_id === data.user_id
                          ? { ...p, last_read_at: data.at }
                          : p,
                      ),
                    }
                  : c,
              ),
            );
          else if (data.type === "conversation") {
            loadList().catch(() => {});
            api<Conversation>("/conversations/" + data.conversation_id)
              .then((fresh) =>
                setConversations((prev) => [
                  ...prev.filter((c) => c.id !== fresh.id),
                  fresh,
                ]),
              )
              .catch(() => {
                setConversations((prev) =>
                  prev.filter((c) => c.id !== data.conversation_id),
                );
                setMessages((prev) => {
                  const next = { ...prev };
                  delete next[data.conversation_id];
                  return next;
                });
                if (activeRef.current === data.conversation_id) {
                  setActive("");
                  setDetails(false);
                  notice("This conversation is no longer available.");
                }
              });
          } else if (data.type === "resync") {
            loadList().catch(() => {});
            if (activeRef.current)
              refresh(activeRef.current, true).catch(() => {});
          } else if (data.type === "error")
            notice(data.detail || "Chat request failed", true);
        } catch {
          notice("Received an unreadable chat event. Reconnecting…", true);
          ws.close();
        }
      };
      ws.onclose = (e) => {
        if (disposed) return;
        if (e.code === 1008) {
          window.dispatchEvent(new Event("session-expired"));
          return;
        }
        setConnection("offline");
        timer = setTimeout(
          connect,
          Math.min(15000, 1000 * 2 ** attempt++) + Math.random() * 500,
        );
      };
      ws.onerror = () => ws.close();
    };
    connect();
    const tick = setInterval(
      () =>
        setTyping((prev) =>
          Object.fromEntries(
            Object.entries(prev).filter(([, at]) => Date.now() - at < 4000),
          ),
        ),
      2000,
    );
    const focus = () => {
      if (document.visibilityState === "visible") {
        loadList().catch(() => {});
        if (activeRef.current) refresh(activeRef.current, true).catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", focus);
    return () => {
      disposed = true;
      clearTimeout(timer);
      clearInterval(tick);
      socket.current?.close();
      document.removeEventListener("visibilitychange", focus);
    };
  }, [loadList, refresh, merge, notice, user.id]);
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    // Synchronize selected conversation with remote history.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh(active)
      .then((last) => {
        if (!cancelled) {
          if (last)
            api(`/conversations/${active}/read`, "POST", {
              last_message_id: last.id,
            })
              .then(() => loadList())
              .catch(() => {});
          setTimeout(() => end.current?.scrollIntoView(), 0);
        }
      })
      .catch((e) => notice(errorText(e), true))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [active, refresh, loadList, notice]);
  async function select(c: Conversation) {
    epoch.current++;
    setLoading(c.id !== active);
    setResults(null);
    setMessageSearch("");
    setActive(c.id);
    setMobile(false);
    setSaved(null);
    setDetails(false);
  }
  async function send(content?: string, media_url?: string) {
    const cid = active;
    if (!cid || busySend.current) return;
    const text = (content ?? drafts[cid] ?? "").trim();
    if (!text && !media_url && !pending[cid]) return;
    const payload = pending[cid] || {
      content: text,
      client_id: crypto.randomUUID(),
      ...(media_url ? { media_url } : {}),
    };
    busySend.current = true;
    setSending(true);
    setPending((prev) => ({ ...prev, [cid]: payload }));
    try {
      const m = await api<Message>(`/conversations/${cid}/messages`, "POST", {
        ...payload,
        conversation_id: cid,
      });
      merge(cid, [m]);
      setDrafts((prev) => ({
        ...prev,
        [cid]: prev[cid]?.trim() === payload.content ? "" : prev[cid] || "",
      }));
      setPending((prev) => {
        const next = { ...prev };
        delete next[cid];
        return next;
      });
      await loadList();
      setTimeout(() => end.current?.scrollIntoView({ behavior: "smooth" }), 0);
    } catch (e) {
      notice(errorText(e) + " Your message is saved here for retry.", true);
    } finally {
      busySend.current = false;
      setSending(false);
    }
  }
  async function upload(f: File) {
    if (busySend.current || pending[active]) return;
    if (f.size > 10 * 1024 * 1024) {
      notice("Maximum file size is 10 MB.", true);
      return;
    }
    const cid = active;
    busySend.current = true;
    setSending(true);
    try {
      const body = new FormData();
      body.append("file", f);
      const result = await api<{ url: string; filename: string }>(
        `/conversations/${cid}/attachments`,
        "POST",
        body,
      );
      const payload = {
        content: result.filename,
        media_url: result.url,
        client_id: crypto.randomUUID(),
      };
      setPending((prev) => ({ ...prev, [cid]: payload }));
      const m = await api<Message>(`/conversations/${cid}/messages`, "POST", {
        ...payload,
        conversation_id: cid,
      });
      merge(cid, [m]);
      setPending((prev) => {
        const next = { ...prev };
        delete next[cid];
        return next;
      });
      await loadList();
    } catch (e) {
      notice(errorText(e), true);
    } finally {
      busySend.current = false;
      setSending(false);
    }
  }
  const list = conversations
    .filter((c) =>
      nameOf(c, user.id).toLowerCase().includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      (summaries[b.id]?.last_message_at || b.created_at).localeCompare(
        summaries[a.id]?.last_message_at || a.created_at,
      ),
    );
  const displayed = saved || results || messages[active] || [];
  return (
    <div className="workspace">
      <aside className="rail">
        <Brand small />
        <div className="rail-main">
          <button
            className={"rail-button " + (!saved ? "selected" : "")}
            aria-label="Conversations"
            title="Conversations"
            onClick={() => {
              setSaved(null);
              setMobile(true);
            }}
          >
            <MessageCircle />
          </button>
          <button
            className={"rail-button " + (saved ? "selected" : "")}
            aria-label="Saved messages"
            title="Saved messages"
            onClick={() =>
              api<Message[]>("/saved")
                .then(setSaved)
                .catch((e) => notice(errorText(e), true))
            }
          >
            <Star />
          </button>
          <button
            className="rail-button"
            aria-label="New conversation"
            title="New conversation"
            onClick={() => setNewChat(true)}
          >
            <Users />
          </button>
        </div>
        <div className="rail-bottom">
          <button
            className="rail-button"
            aria-label={light ? "Use dark appearance" : "Use light appearance"}
            onClick={theme}
          >
            {light ? <Moon /> : <Sun />}
          </button>
          {user.is_admin && (
            <Link className="rail-button" title="Administration" to="/admin">
              <ShieldCheck />
            </Link>
          )}
          <Link className="rail-button" title="Settings" to="/profile">
            <Settings />
          </Link>
          <Link to="/profile" aria-label="Your profile">
            <Avatar name={user.username} />
          </Link>
        </div>
      </aside>
      <aside className={"conversation-panel " + (mobile ? "mobile-open" : "")}>
        <header>
          <h1>
            Messages<span>{conversations.length}</span>
          </h1>
          <button
            className="icon"
            title="Start a conversation"
            aria-label="Start a conversation"
            onClick={() => setNewChat(true)}
          >
            <Plus size={22} />
          </button>
          <button
            className="icon mobile-only"
            aria-label="Close conversation list"
            onClick={() => setMobile(false)}
          >
            <X />
          </button>
        </header>
        <div className="searchbox">
          <Search size={17} />
          <input
            id="conversation-search"
            aria-label="Search conversations"
            placeholder="Find a conversation"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <kbd>⌘ K</kbd>
        </div>
        <div className="list-heading">
          <span>ALL CONVERSATIONS</span>
          <ChevronDown size={14} />
        </div>
        <div className="conversation-list">
          {list.map((c) => (
            <button
              key={c.id}
              className={
                "conversation " + (active === c.id && !saved ? "active" : "")
              }
              onClick={() => select(c)}
            >
              <Avatar name={nameOf(c, user.id)} group={c.is_group} />
              <span className="conversation-copy">
                <span className="conversation-title">
                  {nameOf(c, user.id)}
                  <time>
                    {summaries[c.id]?.last_message_at
                      ? timeOf(summaries[c.id].last_message_at!)
                      : ""}
                  </time>
                </span>
                <span className="conversation-preview">
                  {summaries[c.id]?.content ||
                    (summaries[c.id]?.media_url
                      ? "Attachment"
                      : "Start the conversation")}{" "}
                  {!!summaries[c.id]?.unread && <b>{summaries[c.id].unread}</b>}
                </span>
              </span>
            </button>
          ))}
          {!list.length && (
            <div className="list-empty">
              Your people are one hello away.
              <button className="text-button" onClick={() => setNewChat(true)}>
                Start a conversation
              </button>
            </div>
          )}
          {listMore && (
            <button
              className="text-button full"
              onClick={() =>
                loadList(conversations.length).catch((e) =>
                  notice(errorText(e), true),
                )
              }
            >
              Load more conversations
            </button>
          )}
        </div>
        <div className="connection-status">
          {connection === "connected" ? (
            <Wifi size={14} />
          ) : (
            <WifiOff size={14} />
          )}{" "}
          {connection === "connected"
            ? "Live updates connected"
            : connection === "connecting"
              ? "Connecting…"
              : "Reconnecting — sending remains available"}
        </div>
      </aside>
      <main className="chat-panel">
        <header className="chat-header">
          <button
            className="icon mobile-only"
            aria-label="Open conversations"
            onClick={() => setMobile(true)}
          >
            <Menu />
          </button>
          {current && !saved ? (
            <>
              <Avatar name={title} group={current.is_group} />
              <div className="chat-heading">
                <h2>{title}</h2>
                <span>
                  {current.is_group
                    ? `${current.participants.length} members`
                    : "Direct conversation"}{" "}
                  · {connection === "connected" ? "Connected" : "Reconnecting"}
                </span>
              </div>
            </>
          ) : (
            <div className="chat-heading">
              <h2>{saved ? "Saved messages" : "Your space to connect"}</h2>
              <span>
                {saved
                  ? "The useful things, all in one place."
                  : "A good conversation starts with hello."}
              </span>
            </div>
          )}
          <div className="header-actions">
            {current && !saved && (
              <button
                className={"icon " + (details ? "selected" : "")}
                title="Conversation details"
                aria-label="Conversation details"
                onClick={() => setDetails(!details)}
              >
                <MoreHorizontal />
              </button>
            )}
            <button
              className="icon"
              title="Sign out"
              aria-label="Sign out"
              onClick={logout}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        {current && !saved && (
          <form
            className="message-search"
            onSubmit={async (e) => {
              e.preventDefault();
              const request = ++epoch.current;
              if (!messageSearch.trim()) {
                setResults(null);
                return;
              }
              try {
                const found = await api<Message[]>(
                  `/conversations/${active}/messages?q=${encodeURIComponent(messageSearch)}&limit=100`,
                );
                if (request === epoch.current) setResults(found);
              } catch (err) {
                notice(errorText(err), true);
              }
            }}
          >
            <Search size={14} />
            <input
              value={messageSearch}
              aria-label="Search this conversation"
              placeholder="Search in this conversation…"
              onChange={(e) => setMessageSearch(e.target.value)}
            />
            {results && (
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  epoch.current++;
                  setResults(null);
                  setMessageSearch("");
                }}
              >
                Clear results
              </button>
            )}
          </form>
        )}
        {!current && !saved ? (
          <div className="welcome-chat">
            <div className="welcome-icon">
              <MessageCircle size={42} />
            </div>
            <span className="eyebrow">LESS NOISE. MORE CONNECTION.</span>
            <h2>
              Hello, {user.username.split(" ")[0]}
              <span>✦</span>
            </h2>
            <p>
              Choose a conversation or start something new.
              <br />
              This is where your people come together.
            </p>
            <button className="primary" onClick={() => setNewChat(true)}>
              <Plus size={18} /> New conversation
            </button>
            <div className="welcome-hints">
              <span>
                <ShieldCheck size={16} /> Members-only access
              </span>
              <span>
                <Paperclip size={16} /> File sharing
              </span>
            </div>
          </div>
        ) : (
          <>
            <div className="message-stream" role="log" aria-label="Messages">
              {loading && !saved ? (
                <Loading />
              ) : (
                <>
                  {!saved && !results && more[active] && (
                    <button
                      className="history-button"
                      onClick={async () => {
                        try {
                          const page = await api<Message[]>(
                            `/conversations/${active}/messages?before=${messages[active]?.[0]?.id}&limit=50`,
                          );
                          merge(active, page);
                          setMore((prev) => ({
                            ...prev,
                            [active]: page.length === 50,
                          }));
                        } catch (e) {
                          notice(errorText(e), true);
                        }
                      }}
                    >
                      Load earlier messages
                    </button>
                  )}
                  {!displayed.length && (
                    <div className="stream-empty">
                      <MessageCircle size={28} />
                      <h3>
                        {results
                          ? "No matching messages"
                          : saved
                            ? "Nothing saved yet"
                            : "Say the first hello."}
                      </h3>
                      <p>
                        {saved
                          ? "Use the star next to any message to save it."
                          : "Every conversation starts somewhere."}
                      </p>
                    </div>
                  )}
                  {displayed.map((m, i) => {
                    const own = m.sender_id === user.id;
                    const previous = displayed[i - 1];
                    const day = new Date(m.created_at).toLocaleDateString([], {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    });
                    const showDay =
                      !previous ||
                      new Date(previous.created_at).toDateString() !==
                        new Date(m.created_at).toDateString();
                    const read = current?.participants.some(
                      (p) =>
                        p.user_id !== user.id &&
                        p.last_read_at &&
                        Date.parse(p.last_read_at) >= Date.parse(m.created_at),
                    );
                    return (
                      <div key={m.id}>
                        {showDay && (
                          <div className="date-divider">
                            <span>{day}</span>
                          </div>
                        )}
                        <article className={"message " + (own ? "own" : "")}>
                          {!own && (
                            <Avatar
                              name={m.sender?.username || "Former member"}
                            />
                          )}
                          <div className="message-body">
                            <div className="message-meta">
                              {own
                                ? "You"
                                : m.sender?.username || "Former member"}
                              <time>{timeOf(m.created_at)}</time>
                              {own &&
                                (read ? (
                                  <CheckCheck size={14} className="read" />
                                ) : (
                                  <Check size={14} />
                                ))}
                            </div>
                            <div
                              className={
                                "bubble " + (m.deleted_at ? "deleted" : "")
                              }
                            >
                              {m.media_url ? (
                                <a
                                  className="attachment"
                                  href={BASE + m.media_url}
                                >
                                  <FileText size={24} />
                                  <span>
                                    {m.content || "Download attachment"}
                                    <small>Private attachment</small>
                                  </span>
                                  <Download size={17} />
                                </a>
                              ) : (
                                m.content
                              )}
                            </div>
                            {saved && (
                              <button
                                className="text-button"
                                onClick={() => {
                                  const c = conversations.find(
                                    (c) => c.id === m.conversation_id,
                                  );
                                  if (c) select(c);
                                  else
                                    api<Conversation>(
                                      "/conversations/" + m.conversation_id,
                                    )
                                      .then((c) => {
                                        setConversations((prev) => [
                                          ...prev,
                                          c,
                                        ]);
                                        select(c);
                                      })
                                      .catch((e) => notice(errorText(e), true));
                                }}
                              >
                                Open conversation
                              </button>
                            )}
                          </div>
                          <div className="message-actions">
                            {!m.deleted_at && (
                              <>
                                <button
                                  className="icon"
                                  title={
                                    saved ? "Unsave message" : "Save message"
                                  }
                                  aria-label={
                                    saved ? "Unsave message" : "Save message"
                                  }
                                  onClick={async () => {
                                    try {
                                      await api(
                                        `/messages/${m.id}/saved`,
                                        saved ? "DELETE" : "PUT",
                                      );
                                      if (saved)
                                        setSaved(
                                          saved.filter((x) => x.id !== m.id),
                                        );
                                      notice(
                                        saved
                                          ? "Message removed from saved"
                                          : "Message saved",
                                      );
                                    } catch (e) {
                                      notice(errorText(e), true);
                                    }
                                  }}
                                >
                                  <Star size={14} />
                                </button>
                                {own ? (
                                  <button
                                    className="icon"
                                    title="Delete message"
                                    aria-label="Delete message"
                                    onClick={async () => {
                                      if (
                                        !window.confirm(
                                          "Delete this message for everyone?",
                                        )
                                      )
                                        return;
                                      try {
                                        await api(
                                          `/messages/${m.id}`,
                                          "DELETE",
                                        );
                                        merge(m.conversation_id, [
                                          {
                                            ...m,
                                            content: "Message deleted",
                                            media_url: null,
                                            deleted_at:
                                              new Date().toISOString(),
                                          },
                                        ]);
                                      } catch (e) {
                                        notice(errorText(e), true);
                                      }
                                    }}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                ) : (
                                  <button
                                    className="icon"
                                    title="Report message"
                                    aria-label="Report message"
                                    onClick={() => setReport(m)}
                                  >
                                    <Flag size={14} />
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </article>
                      </div>
                    );
                  })}
                  {saved && saved.length > 0 && saved.length % 50 === 0 && (
                    <button
                      className="history-button"
                      onClick={() =>
                        api<Message[]>("/saved?offset=" + saved.length)
                          .then((rows) =>
                            setSaved((prev) =>
                              prev ? [...prev, ...rows] : prev,
                            ),
                          )
                          .catch((e) => notice(errorText(e), true))
                      }
                    >
                      Load more saved messages
                    </button>
                  )}
                  <div ref={end} />
                </>
              )}
            </div>
            {!saved && (
              <div className="composer-area">
                <div className="typing-line">
                  {typing[active]
                    ? "Someone is typing…"
                    : pending[active]
                      ? "Message not confirmed. Retry to send safely without duplicates."
                      : " "}
                </div>
                {pending[active] && !sending && (
                  <button
                    className="text-button"
                    onClick={() => {
                      if (
                        !window.confirm(
                          "This message may already have been sent. Dismiss its retry and check the conversation history?",
                        )
                      )
                        return;
                      const cid = active;
                      setDrafts((prev) => ({ ...prev, [cid]: "" }));
                      setPending((prev) => {
                        const next = { ...prev };
                        delete next[cid];
                        return next;
                      });
                      refresh(cid, true).catch((e) =>
                        notice(errorText(e), true),
                      );
                    }}
                  >
                    Dismiss unconfirmed send
                  </button>
                )}
                <form
                  className="composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    send();
                  }}
                >
                  <input
                    ref={file}
                    type="file"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) upload(f);
                      e.target.value = "";
                    }}
                  />
                  <button
                    type="button"
                    className="icon"
                    aria-label="Attach a file"
                    disabled={sending || !!pending[active]}
                    onClick={() => file.current?.click()}
                  >
                    <Paperclip size={21} />
                  </button>
                  <textarea
                    aria-label="Message"
                    placeholder={"Message " + title + "…"}
                    maxLength={10000}
                    rows={1}
                    value={drafts[active] || ""}
                    disabled={!!pending[active]}
                    onChange={(e) => {
                      setDrafts((prev) => ({
                        ...prev,
                        [active]: e.target.value,
                      }));
                      if (
                        Date.now() - lastType.current > 2500 &&
                        socket.current?.readyState === 1
                      ) {
                        lastType.current = Date.now();
                        socket.current.send(
                          JSON.stringify({
                            type: "typing",
                            conversation_id: active,
                          }),
                        );
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        send();
                      }
                    }}
                  />
                  <button
                    className="send-button"
                    type="submit"
                    disabled={
                      sending || (!pending[active] && !drafts[active]?.trim())
                    }
                    aria-label={
                      pending[active] ? "Retry message" : "Send message"
                    }
                  >
                    {sending ? (
                      <LoaderCircle className="spin" size={18} />
                    ) : pending[active] ? (
                      <span>Retry</span>
                    ) : (
                      <Send size={19} />
                    )}
                  </button>
                </form>
                <div className="composer-hint">
                  Enter to send · Shift + Enter for a new line
                  <span>Shared with conversation members</span>
                </div>
              </div>
            )}
          </>
        )}
      </main>
      {details && current && (
        <Details
          conversation={current}
          user={user}
          notice={notice}
          close={() => setDetails(false)}
          changed={async () => {
            await loadList();
            const fresh = await api<Conversation>("/conversations/" + active);
            setConversations((prev) =>
              prev.map((c) => (c.id === active ? fresh : c)),
            );
          }}
          left={() => {
            setActive("");
            setDetails(false);
            loadList();
          }}
        />
      )}
      {newChat && (
        <NewConversation
          user={user}
          notice={notice}
          close={() => setNewChat(false)}
          created={(c) => {
            setConversations((prev) => [
              c,
              ...prev.filter((x) => x.id !== c.id),
            ]);
            select(c);
            setNewChat(false);
            loadList();
          }}
        />
      )}
      {report && (
        <Modal title="Report this message" close={() => setReport(null)}>
          <p className="muted">
            An administrator will review this message and your reason.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api(`/messages/${report.id}/report`, "POST", {
                  reason: new FormData(e.currentTarget).get("reason"),
                });
                notice("Report sent for review");
                setReport(null);
              } catch (err) {
                notice(errorText(err), true);
              }
            }}
          >
            <label>
              Reason
              <textarea name="reason" minLength={3} maxLength={1000} required />
            </label>
            <button className="primary full">Submit report</button>
          </form>
        </Modal>
      )}
    </div>
  );
}
