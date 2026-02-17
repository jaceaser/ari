import { auth } from "@/app/(auth)/auth";
import { proxyToBackend } from "@/lib/api-proxy";

export async function POST() {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await proxyToBackend("/billing/create-checkout", {
    method: "POST",
  });

  const data = await res.json();
  return Response.json(data, { status: res.status });
}
