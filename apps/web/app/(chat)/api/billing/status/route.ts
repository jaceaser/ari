import { auth } from "@/app/(auth)/auth";
import { proxyToBackend } from "@/lib/api-proxy";

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ active: false, plan: null, expires_at: null });
  }

  try {
    const res = await proxyToBackend("/billing/status");
    const data = await res.json();
    return Response.json(data);
  } catch {
    return Response.json({ active: false, plan: null, expires_at: null });
  }
}
