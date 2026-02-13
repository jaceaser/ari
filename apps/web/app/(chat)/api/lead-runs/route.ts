import { auth } from "@/app/(auth)/auth";
import { checkBackendConfig, proxyToBackend } from "@/lib/api-proxy";

export async function GET() {
  const configErr = checkBackendConfig();
  if (configErr) return configErr;

  const session = await auth();
  if (!session?.user) {
    return new Response("Unauthorized", { status: 401 });
  }

  const res = await proxyToBackend("/lead-runs");
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    return Response.json(data, { status: res.status });
  } catch {
    console.error("[lead-runs] Non-JSON response from backend:", res.status, text.slice(0, 200));
    return Response.json([], { status: 200 });
  }
}
