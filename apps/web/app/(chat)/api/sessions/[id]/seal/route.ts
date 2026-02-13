import { auth } from "@/app/(auth)/auth";
import { checkBackendConfig, proxyToBackend } from "@/lib/api-proxy";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const configErr = checkBackendConfig();
  if (configErr) return configErr;

  const session = await auth();
  if (!session?.user) {
    return new Response("Unauthorized", { status: 401 });
  }

  const { id } = await params;
  const res = await proxyToBackend(`/sessions/${id}/seal`, { method: "POST" });
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    return Response.json(data, { status: res.status });
  } catch {
    console.error("[seal] Non-JSON response from backend:", res.status, text.slice(0, 200));
    return Response.json({ error: "Invalid backend response" }, { status: 502 });
  }
}
