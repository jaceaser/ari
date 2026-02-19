/**
 * Server-side API client — replaces SQLite queries.ts.
 *
 * Every function proxies to the Python API backend via JWT-authenticated fetch.
 * Function signatures match the old queries.ts interface for minimal caller changes.
 */
import "server-only";

import type { ArtifactKind } from "@/components/artifact";
import type { VisibilityType } from "@/components/visibility-selector";

import { proxyToBackend } from "./api-proxy";
import type {
  Chat,
  DBMessage,
  Document,
  Suggestion,
  User,
  Vote,
} from "./db/schema";
import { generateUUID } from "./utils";

// ── Users ──

export async function getUser(email: string): Promise<User[]> {
  // Password-based user lookup is no longer supported without SQLite.
  // Magic link auth (PR9c) will replace this.
  // Return empty to indicate user not found.
  return [];
}

export async function createUser(_email: string, _password: string) {
  // Password-based user creation is no longer supported without SQLite.
  // Magic link auth (PR9c) will replace this.
  throw new Error("Password-based registration disabled. Use magic link auth.");
}

export async function createGuestUser() {
  // Guest users are created in-memory by NextAuth, no DB needed.
  const id = generateUUID();
  return [{ id, email: `guest-${Date.now()}` }];
}

// ── Chats / Sessions ──

export async function saveChat({
  id,
  userId,
  title,
  visibility,
}: {
  id: string;
  userId: string;
  title: string;
  visibility: VisibilityType;
}) {
  const res = await proxyToBackend("/sessions", {
    method: "POST",
    body: { id, title },
  });
  if (!res.ok) {
    // Session may already exist (409), which is fine
    if (res.status !== 409) {
      console.warn("saveChat failed:", res.status);
    }
  }
}

export async function getChatById({
  id,
}: { id: string }): Promise<Chat | null> {
  let res: Response;
  try {
    res = await proxyToBackend(`/sessions/${id}`);
  } catch {
    return null;
  }
  if (!res.ok) return null;
  try {
    const data = await res.json();
    return {
      id: data.id,
      title: data.title || "",
      createdAt: data.created_at
        ? new Date(data.created_at).getTime()
        : Date.now(),
      userId: data.userId || data.user_id || "",
      visibility: "private",
      status: data.status,
    };
  } catch {
    return null;
  }
}

export async function getChatsByUserId({
  id,
  limit,
  startingAfter,
  endingBefore,
}: {
  id: string;
  limit: number;
  startingAfter: string | null;
  endingBefore: string | null;
}) {
  let res: Response;
  try {
    res = await proxyToBackend("/sessions");
  } catch (err) {
    console.warn("getChatsByUserId: backend unreachable:", (err as Error).message);
    return { chats: [], hasMore: false };
  }
  if (!res.ok) return { chats: [], hasMore: false };

  let sessions: Array<{
    id: string;
    title?: string | null;
    status?: string;
    created_at?: string;
    userId?: string;
  }>;
  try {
    sessions = await res.json();
  } catch {
    return { chats: [], hasMore: false };
  }

  if (!Array.isArray(sessions)) return { chats: [], hasMore: false };

  // Deduplicate by id (Cosmos can occasionally return dupes on revalidation)
  const seen = new Set<string>();
  const uniqueSessions = sessions.filter((s) => {
    if (seen.has(s.id)) return false;
    seen.add(s.id);
    return true;
  });

  let chats: Chat[] = uniqueSessions.map((s) => ({
    id: s.id,
    title: s.title || "",
    createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
    userId: s.userId || id,
    visibility: "private",
    status: s.status || "active",
  }));

  // Sort newest first
  chats.sort((a, b) => b.createdAt - a.createdAt);

  // Cursor-based pagination: slice to the window requested
  if (endingBefore) {
    const idx = chats.findIndex((c) => c.id === endingBefore);
    if (idx !== -1) {
      chats = chats.slice(idx + 1);
    }
  } else if (startingAfter) {
    const idx = chats.findIndex((c) => c.id === startingAfter);
    if (idx !== -1) {
      chats = chats.slice(0, idx);
    }
  }

  const hasMore = chats.length > limit;
  return { chats: chats.slice(0, limit), hasMore };
}

export async function deleteChatById({ id }: { id: string }) {
  const res = await proxyToBackend(`/sessions/${id}`, { method: "DELETE" });
  return { id, deleted: res.ok };
}

export async function deleteAllChatsByUserId({
  userId,
}: { userId: string }) {
  // Backend doesn't have bulk delete — iterate sessions
  const res = await proxyToBackend("/sessions");
  if (!res.ok) return { deletedCount: 0 };
  const sessions = (await res.json()) as Array<{ id: string }>;
  let deletedCount = 0;
  for (const s of sessions) {
    const delRes = await proxyToBackend(`/sessions/${s.id}`, {
      method: "DELETE",
    });
    if (delRes.ok) deletedCount++;
  }
  return { deletedCount };
}

export async function updateChatTitleById({
  chatId,
  title,
}: {
  chatId: string;
  title: string;
}) {
  await proxyToBackend(`/sessions/${chatId}`, {
    method: "PATCH",
    body: { title },
  });
}

export async function updateChatVisibilityById({
  chatId,
  visibility,
}: {
  chatId: string;
  visibility: "private" | "public";
}) {
  // Visibility is a frontend concept — no backend equivalent currently.
  // No-op; could be added to session metadata later.
}

// ── Messages ──

export async function saveMessages({
  messages,
}: { messages: DBMessage[] }) {
  if (messages.length === 0) return;
  const chatId = messages[0].chatId;
  await proxyToBackend("/data/messages", {
    method: "POST",
    body: { chatId, messages },
  });
}

export async function getMessagesByChatId({
  id,
}: { id: string }): Promise<DBMessage[]> {
  let res: Response;
  try {
    res = await proxyToBackend(`/sessions/${id}/messages`);
  } catch {
    return [];
  }
  if (!res.ok) return [];
  const apiMessages = (await res.json()) as Array<{
    id: string;
    role: string;
    content: string;
    parts?: string;
    attachments?: string;
    created_at?: string;
    createdAt?: string;
  }>;
  return apiMessages.map((m) => ({
    id: m.id,
    chatId: id,
    role: m.role,
    parts: m.parts || JSON.stringify([{ type: "text", text: m.content }]),
    attachments: m.attachments || "[]",
    createdAt: m.created_at
      ? new Date(m.created_at).getTime()
      : m.createdAt
        ? typeof m.createdAt === "number"
          ? m.createdAt
          : new Date(m.createdAt).getTime()
        : Date.now(),
  }));
}

export async function getMessageById({
  id,
}: { id: string }): Promise<DBMessage[]> {
  const res = await proxyToBackend(`/data/messages/${id}`);
  if (!res.ok) return [];
  const msg = await res.json();
  return [
    {
      id: msg.id,
      chatId: msg.sessionId || msg.chatId || "",
      role: msg.role,
      parts: msg.parts || msg.content || "",
      attachments: msg.attachments || "[]",
      createdAt: msg.createdAt
        ? typeof msg.createdAt === "number"
          ? msg.createdAt
          : new Date(msg.createdAt).getTime()
        : Date.now(),
    },
  ];
}

export async function updateMessage({
  id,
  parts,
}: {
  id: string;
  parts: DBMessage["parts"];
}) {
  await proxyToBackend(`/data/messages/${id}`, {
    method: "PATCH",
    body: { parts },
  });
}

export async function deleteMessagesByChatIdAfterTimestamp({
  chatId,
  timestamp,
}: {
  chatId: string;
  timestamp: number;
}) {
  await proxyToBackend("/data/messages/delete-after", {
    method: "POST",
    body: { chatId, timestamp },
  });
}

export async function getMessageCountByUserId({
  id,
  differenceInHours,
}: {
  id: string;
  differenceInHours: number;
}): Promise<number> {
  const res = await proxyToBackend(
    `/data/messages/count?hours=${differenceInHours}`
  );
  if (!res.ok) return 0;
  const data = await res.json();
  return data.count ?? 0;
}

// ── Documents ──

export async function saveDocument({
  id,
  title,
  kind,
  content,
  userId,
}: {
  id: string;
  title: string;
  kind: ArtifactKind;
  content: string;
  userId: string;
}) {
  const res = await proxyToBackend("/data/documents", {
    method: "POST",
    body: { id, title, kind, content },
  });
  if (!res.ok) return [];
  return [await res.json()];
}

export async function getDocumentsById({
  id,
}: { id: string }): Promise<Document[]> {
  const res = await proxyToBackend(`/data/documents/${id}`);
  if (!res.ok) return [];
  const docs = await res.json();
  // Normalize Cosmos docs to match our Document interface
  return (Array.isArray(docs) ? docs : [docs]).map((d: any) => ({
    id: d.documentId || d.id,
    createdAt:
      typeof d.createdAt === "number"
        ? d.createdAt
        : new Date(d.createdAt).getTime(),
    title: d.title,
    content: d.content ?? null,
    kind: d.kind,
    userId: d.userId,
  }));
}

export async function getDocumentById({
  id,
}: { id: string }): Promise<Document | undefined> {
  const res = await proxyToBackend(`/data/documents/${id}?latest=true`);
  if (!res.ok) return undefined;
  const d = await res.json();
  return {
    id: d.documentId || d.id,
    createdAt:
      typeof d.createdAt === "number"
        ? d.createdAt
        : new Date(d.createdAt).getTime(),
    title: d.title,
    content: d.content ?? null,
    kind: d.kind,
    userId: d.userId,
  };
}

export async function deleteDocumentsByIdAfterTimestamp({
  id,
  timestamp,
}: {
  id: string;
  timestamp: number;
}) {
  const res = await proxyToBackend(`/data/documents/${id}/delete-after`, {
    method: "POST",
    body: { timestamp },
  });
  if (!res.ok) return [];
  return res.json();
}

// ── Suggestions ──

export async function saveSuggestions({
  suggestions,
}: {
  suggestions: Suggestion[];
}) {
  await proxyToBackend("/data/suggestions", {
    method: "POST",
    body: { suggestions },
  });
}

export async function getSuggestionsByDocumentId({
  documentId,
}: {
  documentId: string;
}): Promise<Suggestion[]> {
  const res = await proxyToBackend(
    `/data/suggestions?documentId=${documentId}`
  );
  if (!res.ok) return [];
  return res.json();
}

// ── Votes ──

export async function voteMessage({
  chatId,
  messageId,
  type,
}: {
  chatId: string;
  messageId: string;
  type: "up" | "down";
}) {
  await proxyToBackend("/data/votes", {
    method: "POST",
    body: { chatId, messageId, type },
  });
}

export async function getVotesByChatId({
  id,
}: { id: string }): Promise<Vote[]> {
  const res = await proxyToBackend(`/data/votes?chatId=${id}`);
  if (!res.ok) return [];
  return res.json();
}

// ── Streams (removed — Redis no longer used) ──

export async function createStreamId(_args: {
  streamId: string;
  chatId: string;
}) {
  // No-op: Redis-based resumable streams removed.
}

export async function getStreamIdsByChatId(_args: {
  chatId: string;
}): Promise<string[]> {
  return [];
}
