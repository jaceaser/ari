/**
 * Legacy /api/chat route — no longer used.
 *
 * All chat traffic now routes through /api/chat/openai which proxies to the
 * Python backend API (Azure OpenAI + MCP tool orchestration).
 *
 * This stub exists only to return a clear error if something still hits this
 * endpoint directly.
 */

export const maxDuration = 60;

export async function POST(_request: Request) {
  return Response.json(
    {
      code: "bad_request:api",
      cause: "This endpoint is deprecated. Chat is routed through the backend API.",
    },
    { status: 410 }
  );
}
