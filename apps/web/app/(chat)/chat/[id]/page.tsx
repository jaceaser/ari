import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";

import { auth } from "@/app/(auth)/auth";
import { Chat } from "@/components/chat";
import { DataStreamHandler } from "@/components/data-stream-handler";
import { isExternalBackend, proxyToBackend } from "@/lib/api-proxy";
import { getChatById, getMessagesByChatId } from "@/lib/db/queries";
import type { ChatMessage } from "@/lib/types";
import { convertToUIMessages } from "@/lib/utils";

export default function Page(props: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<div className="flex h-dvh" />}>
      <ChatPage params={props.params} />
    </Suspense>
  );
}

async function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  // ── External backend: load session + messages from API ──
  if (isExternalBackend()) {
    const session = await auth();
    if (!session?.user) {
      redirect("/api/auth/guest");
    }

    let uiMessages: ChatMessage[] = [];
    let isSealed = false;

    try {
      const [sessionRes, messagesRes] = await Promise.all([
        proxyToBackend(`/sessions/${id}`),
        proxyToBackend(`/sessions/${id}/messages`),
      ]);

      if (!sessionRes.ok) {
        redirect("/");
      }

      const sessionData = await sessionRes.json();
      isSealed = sessionData.status === "sealed";

      if (messagesRes.ok) {
        const apiMessages = (await messagesRes.json()) as Array<{
          id: string;
          role: string;
          content: string;
          created_at: string;
        }>;

        uiMessages = apiMessages.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          parts: [{ type: "text" as const, text: m.content }],
          metadata: { createdAt: m.created_at },
        }));
      }
    } catch {
      redirect("/");
    }

    return (
      <>
        <Chat
          autoResume={false}
          id={id}
          initialMessages={uiMessages}
          initialVisibilityType="private"
          isReadonly={isSealed}
        />
        <DataStreamHandler />
      </>
    );
  }

  // ── Local SQLite path (unchanged) ──
  const chat = await getChatById({ id });

  if (!chat) {
    redirect("/");
  }

  const session = await auth();

  if (!session) {
    redirect("/api/auth/guest");
  }

  if (chat.visibility === "private") {
    if (!session.user) {
      return notFound();
    }

    if (session.user.id !== chat.userId) {
      return notFound();
    }
  }

  const messagesFromDb = await getMessagesByChatId({
    id,
  });

  const uiMessages = convertToUIMessages(messagesFromDb);

  return (
    <>
      <Chat
        autoResume={true}
        id={chat.id}
        initialMessages={uiMessages}
        initialVisibilityType={chat.visibility}
        isReadonly={session?.user?.id !== chat.userId}
      />
      <DataStreamHandler />
    </>
  );
}
