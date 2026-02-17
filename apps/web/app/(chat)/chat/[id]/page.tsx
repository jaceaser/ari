import { redirect } from "next/navigation";
import { Suspense } from "react";

import { auth } from "@/app/(auth)/auth";
import { Chat } from "@/components/chat";
import { DataStreamHandler } from "@/components/data-stream-handler";
import { getChatById, getMessagesByChatId } from "@/lib/api-client";
import { convertToUIMessages } from "@/lib/utils";
import type { VisibilityType } from "@/components/visibility-selector";

export default function Page(props: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<div className="flex h-dvh" />}>
      <ChatPage params={props.params} />
    </Suspense>
  );
}

async function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const session = await auth();
  if (!session?.user) {
    redirect("/api/auth/guest");
  }

  const chat = await getChatById({ id });

  if (!chat) {
    redirect("/");
  }

  const messagesFromDb = await getMessagesByChatId({ id });
  const uiMessages = convertToUIMessages(messagesFromDb);

  const isSealed = chat.status === "sealed";
  const isReadonly = isSealed || session.user.id !== chat.userId;

  return (
    <>
      <Chat
        autoResume={false}
        id={chat.id}
        initialMessages={uiMessages}
        initialVisibilityType={(chat.visibility || "private") as VisibilityType}
        isReadonly={isReadonly}
      />
      <DataStreamHandler />
    </>
  );
}
