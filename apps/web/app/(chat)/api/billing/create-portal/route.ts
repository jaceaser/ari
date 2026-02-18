import { auth } from "@/app/(auth)/auth";
import { proxyToBackend } from "@/lib/api-proxy";

export async function POST() {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const res = await proxyToBackend("/billing/create-portal", {
      method: "POST",
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json(
      { error: "Failed to create portal session" },
      { status: 500 }
    );
  }
}
