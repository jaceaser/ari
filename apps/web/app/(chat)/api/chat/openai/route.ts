import {
  createUIMessageStream,
  createUIMessageStreamResponse,
} from "ai";

import {
  getAuthenticatedJwt,
} from "@/lib/api-proxy";
import {
  writeOpenAiSseToUiStream,
} from "@/lib/sse-parser";

import { proxyToBackend } from "@/lib/api-proxy";

// ── Types ──

type IncomingMessagePart = { type?: string; text?: string; url?: string; mediaType?: string };
type IncomingMessage = { role?: string; parts?: IncomingMessagePart[] };

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
    return Response.json(
      { code: "bad_request:api", cause: "Invalid JSON request body" },
      { status: 400 }
    );
  }

  const sourceMessages = Array.isArray(requestBody.messages)
    ? requestBody.messages
    : requestBody.message
      ? [requestBody.message]
      : [];

  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    return Response.json(
      { code: "bad_request:api", cause: "Backend API URL not configured. Set API_BASE_URL or NEXT_PUBLIC_API_URL." },
      { status: 503 }
    );
  }

  const sessionId = requestBody.session_id;
  if (!sessionId) {
    return Response.json(
      { code: "bad_request:api", cause: "Missing session_id in request body" },
      { status: 400 }
    );
  }

  const content = extractLastUserText(sourceMessages);
  if (!content) {
    return Response.json(
      { code: "bad_request:api", cause: "No user message content found" },
      { status: 400 }
    );
  }

  const { images, documents } = extractFileUrls(sourceMessages);

  let jwt: string;
  try {
    jwt = await getAuthenticatedJwt();
  } catch (err) {
    console.error("[openai/route] Auth failed:", (err as Error).message);
    return Response.json(
      { code: "unauthorized:chat", cause: "Authentication required. Ensure JWT_SECRET is configured." },
      { status: 401 }
    );
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
    // Try to parse backend error JSON for better error messages
    try {
      const parsed = JSON.parse(text);
      return Response.json(
        { code: "bad_request:api", cause: parsed.detail || parsed.error || text },
        { status: upstreamResponse.status }
      );
    } catch {
      return Response.json(
        { code: "bad_request:api", cause: text || "Upstream API request failed" },
        { status: upstreamResponse.status }
      );
    }
  }

  if (!upstreamResponse.body) {
    return Response.json(
      { code: "bad_request:api", cause: "Empty upstream response body" },
      { status: 502 }
    );
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
