import { auth } from "@/app/(auth)/auth";
import { proxyToBackend } from "@/lib/api-proxy";

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const newEmail = body?.email;

  if (!newEmail || typeof newEmail !== "string" || !newEmail.includes("@")) {
    return Response.json({ error: "Valid email required" }, { status: 400 });
  }

  try {
    const res = await proxyToBackend("/auth/update-email", {
      method: "POST",
      body: { email: newEmail },
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json(
      { error: "Failed to update email" },
      { status: 500 }
    );
  }
}
