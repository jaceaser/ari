import {
  createUIMessageStream,
  createUIMessageStreamResponse,
} from "ai";

import {
  checkBackendConfig,
  getAuthenticatedJwt,
  isExternalBackend,
} from "@/lib/api-proxy";
import {
  writeOpenAiSseToUiStream,
} from "@/lib/sse-parser";

import { proxyToBackend } from "@/lib/api-proxy";

// ── Types ──

type IncomingMessagePart = { type?: string; text?: string; url?: string; mediaType?: string };
type IncomingMessage = { role?: string; parts?: IncomingMessagePart[] };
type OpenAIMessage = { role: "system" | "user" | "assistant"; content: string };

function isConversationRole(value: string): value is OpenAIMessage["role"] {
  return value === "system" || value === "user" || value === "assistant";
}

function toOpenAIMessages(messages: IncomingMessage[]): OpenAIMessage[] {
  const result: OpenAIMessage[] = [];
  for (const message of messages) {
    const role = message.role;
    if (!role || !isConversationRole(role)) continue;

    const text = (Array.isArray(message.parts) ? message.parts : [])
      .filter((p) => p?.type === "text" && typeof p.text === "string")
      .map((p) => p.text!.trim())
      .filter(Boolean)
      .join("\n");

    if (!text) continue;
    result.push({ role, content: text });
  }
  return result;
}

function getApiBaseUrl(): string | null {
  const url =
    process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || null;
  if (!url) return null;
  return url.replace(/\/+$/, "");
}

/** Check if this looks like the first user message in the conversation. */
function isFirstUserMessage(messages: IncomingMessage[]): boolean {
  return messages.filter((m) => m.role === "user").length <= 1;
}

/** Create a short title from user text (first sentence or first 80 chars). */
function deriveTitle(text: string): string {
  // Take the first sentence or first 80 chars, whichever is shorter
  const firstSentence = text.split(/[.!?\n]/)[0]?.trim() || text;
  const title = firstSentence.length > 80
    ? firstSentence.slice(0, 77) + "..."
    : firstSentence;
  return title;
}

/** Fire-and-forget: update session title on the backend. */
function setSessionTitle(sessionId: string, title: string): void {
  proxyToBackend(`/sessions/${sessionId}`, {
    method: "PATCH",
    body: { title },
  }).catch((err) => {
    console.error("[openai/route] Failed to set session title:", (err as Error).message);
  });
}

/** Extract the last user message text from UI message parts. */
function extractLastUserText(messages: IncomingMessage[]): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role !== "user") continue;
    const parts = messages[i].parts ?? [];
    const text = parts
      .filter((p) => p?.type === "text" && typeof p.text === "string")
      .map((p) => p.text!.trim())
      .filter(Boolean)
      .join("\n");
    if (text) return text;
  }
  return "";
}

/** Extract file URLs from the last user message's file parts, split by type. */
function extractFileUrls(messages: IncomingMessage[]): {
  images: string[];
  documents: { url: string; name: string; mediaType: string }[];
} {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role !== "user") continue;
    const parts = messages[i].parts ?? [];
    const fileParts = parts.filter(
      (p) => p?.type === "file" && typeof p.url === "string",
    );
    return {
      images: fileParts
        .filter((p) => p.mediaType?.startsWith("image/"))
        .map((p) => p.url!),
      documents: fileParts
        .filter((p) => !p.mediaType?.startsWith("image/"))
        .map((p) => ({
          url: p.url!,
          name: p.mediaType ?? "application/octet-stream",
          mediaType: p.mediaType ?? "application/octet-stream",
        })),
    };
  }
  return { images: [], documents: [] };
}

// ── Route handler ──

export async function POST(request: Request) {
  let requestBody: {
    messages?: IncomingMessage[];
    message?: IncomingMessage;
    session_id?: string;
  };

  try {
    requestBody = (await request.json()) as typeof requestBody;
  } catch {
    return new Response("Invalid JSON request body", { status: 400 });
  }

  const sourceMessages = Array.isArray(requestBody.messages)
    ? requestBody.messages
    : requestBody.message
      ? [requestBody.message]
      : [];

  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    return new Response(
      "Missing backend URL. Set API_BASE_URL or NEXT_PUBLIC_API_URL.",
      { status: 500 }
    );
  }

  // ── Session-based path: route to /sessions/:id/messages ──
  // Requires both NEXT_PUBLIC_API_URL and JWT_SECRET to be configured.
  const sessionId = requestBody.session_id;
  const jwtConfigured = Boolean((process.env.JWT_SECRET || "").trim());
  if (sessionId && isExternalBackend() && jwtConfigured) {
    const content = extractLastUserText(sourceMessages);
    if (!content) {
      return new Response("No user message content found", { status: 400 });
    }
    const { images, documents } = extractFileUrls(sourceMessages);

    let jwt: string;
    try {
      jwt = await getAuthenticatedJwt();
    } catch (err) {
      console.error("[openai/route] Auth failed:", (err as Error).message);
      return new Response("Authentication required", { status: 401 });
    }

    const upstreamResponse = await fetch(
      `${apiBaseUrl}/sessions/${sessionId}/messages`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${jwt}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content,
          ...(images.length > 0 && { images }),
          ...(documents.length > 0 && { documents }),
        }),
      }
    );

    if (!upstreamResponse.ok) {
      const text = await upstreamResponse.text();
      return new Response(text || "Upstream API request failed", {
        status: upstreamResponse.status,
      });
    }

    if (!upstreamResponse.body) {
      return new Response("Empty upstream response body", { status: 502 });
    }

    // Set session title from first user message (fire-and-forget)
    if (isFirstUserMessage(sourceMessages)) {
      const title = deriveTitle(content);
      if (title) {
        setSessionTitle(sessionId, title);
      }
    }

    const stream = createUIMessageStream({
      execute: async ({ writer }) => {
        await writeOpenAiSseToUiStream(upstreamResponse.body!, writer);
      },
    });

    return createUIMessageStreamResponse({ stream });
  }

  // ── Legacy path: route to /v1/chat/completions ──
  const messages = toOpenAIMessages(sourceMessages);
  if (messages.length === 0) {
    return new Response("No valid conversation messages found", { status: 400 });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (process.env.BACKEND_API_BEARER_TOKEN) {
    headers.Authorization = `Bearer ${process.env.BACKEND_API_BEARER_TOKEN}`;
  }

  const upstreamResponse = await fetch(`${apiBaseUrl}/v1/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: "gpt-5.2-chat",
      messages,
      stream: true,
    }),
  });

  if (!upstreamResponse.ok) {
    const text = await upstreamResponse.text();
    return new Response(text || "Upstream API request failed", {
      status: upstreamResponse.status,
    });
  }

  if (!upstreamResponse.body) {
    return new Response("Empty upstream response body", { status: 502 });
  }

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      await writeOpenAiSseToUiStream(upstreamResponse.body!, writer);
    },
  });

  return createUIMessageStreamResponse({ stream });
}
