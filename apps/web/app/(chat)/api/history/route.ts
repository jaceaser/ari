import type { NextRequest } from "next/server";
import { auth } from "@/app/(auth)/auth";
import { isExternalBackend, proxyToBackend } from "@/lib/api-proxy";
import { deleteAllChatsByUserId, getChatsByUserId } from "@/lib/db/queries";
import { ChatSDKError } from "@/lib/errors";

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return new ChatSDKError("unauthorized:chat").toResponse();
  }

  // ── External backend: load sessions from API ──
  if (isExternalBackend()) {
    try {
      const res = await proxyToBackend("/sessions");
      if (!res.ok) {
        return Response.json({ chats: [], hasMore: false });
      }
      const sessions = (await res.json()) as Array<{
        id: string;
        title?: string | null;
        status?: string;
        created_at?: string;
        sealed_at?: string | null;
      }>;

      const chats = sessions.map((s) => ({
        id: s.id,
        title: s.title || "Untitled",
        createdAt: s.created_at ? new Date(s.created_at) : new Date(),
        userId: session.user!.id,
        visibility: "private" as const,
        status: s.status || "active",
      }));

      return Response.json({ chats, hasMore: false });
    } catch {
      return Response.json({ chats: [], hasMore: false });
    }
  }

  // ── Local SQLite path (unchanged) ──
  const { searchParams } = request.nextUrl;
  const limit = Number.parseInt(searchParams.get("limit") || "10", 10);
  const startingAfter = searchParams.get("starting_after");
  const endingBefore = searchParams.get("ending_before");

  if (startingAfter && endingBefore) {
    return new ChatSDKError(
      "bad_request:api",
      "Only one of starting_after or ending_before can be provided."
    ).toResponse();
  }

  const chats = await getChatsByUserId({
    id: session.user.id,
    limit,
    startingAfter,
    endingBefore,
  });

  return Response.json(chats);
}

export async function DELETE() {
  const session = await auth();
  if (!session?.user) {
    return new ChatSDKError("unauthorized:chat").toResponse();
  }

  // External backend: no-op for now (API doesn't have bulk delete)
  if (isExternalBackend()) {
    return Response.json({ success: true }, { status: 200 });
  }

  const result = await deleteAllChatsByUserId({ userId: session.user.id });
  return Response.json(result, { status: 200 });
}
