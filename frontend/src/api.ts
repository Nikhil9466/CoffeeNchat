export interface Person {
  id: string;
  username: string;
  bio: string;
  profile_picture_url: string | null;
}
export interface User extends Person {
  email: string;
  is_admin: boolean;
  created_at: string;
}
export interface Member {
  user_id: string;
  role: string;
  user: Person;
  last_read_at: string | null;
}
export interface Conversation {
  id: string;
  name: string | null;
  is_group: boolean;
  created_at: string;
  participants: Member[];
}
export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  content: string | null;
  media_url: string | null;
  client_id: string | null;
  created_at: string;
  deleted_at: string | null;
  sender: Person | null;
}
export interface Summary {
  id: string;
  content: string | null;
  last_message_at: string | null;
  media_url: string | null;
  unread: number;
}
export interface Session {
  id: string;
  label: string;
  current: boolean;
  created_at: string;
  expires_at: string;
}
export interface FileItem {
  id: string;
  filename: string;
  url: string;
  created_at: string;
}
export const BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(
  /\/$/,
  "",
);
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch(BASE + path, {
    method,
    credentials: "include",
    signal,
    headers: body && !form ? { "Content-Type": "application/json" } : undefined,
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (
      response.status === 401 &&
      !["/users/login", "/users/me"].includes(path)
    )
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request failed. Please try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function socketUrl() {
  const url = new URL(BASE, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname += "/ws/chat";
  return url.toString();
}
export const nameOf = (c: Conversation, uid: string) =>
  c.is_group
    ? c.name || "Group"
    : c.participants.find((p) => p.user_id !== uid)?.user?.username ||
      "Former member";
export const timeOf = (date: string) =>
  new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "Something went wrong.";
