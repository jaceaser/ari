import { cookies } from "next/headers";
import { Suspense } from "react";
import { Chat } from "@/components/chat";
import { DataStreamHandler } from "@/components/data-stream-handler";
import { proxyToBackend } from "@/lib/api-proxy";
import { generateUUID } from "@/lib/utils";

export default function Page() {
  return (
    <Suspense fallback={<div className="flex h-dvh" />}>
      <NewChatPage />
    </Suspense>
  );
}

async function NewChatPage() {
  await cookies(); // access dynamic data before Math.random()
  const id = generateUUID();

  // Create a backend session so the ID is registered before the first message
  try {
    const res = await proxyToBackend("/sessions", {
      method: "POST",
      body: { id },
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      console.error("[page] Session creation failed:", res.status, text.slice(0, 200));
    }
  } catch (err) {
    console.error("[page] Session creation error:", (err as Error).message);
  }

  return (
    <>
      <Chat
        autoResume={false}
        id={id}
        initialMessages={[]}
        initialVisibilityType="private"
        isReadonly={false}
        key={id}
      />
      <DataStreamHandler />
    </>
  );
}
