/**
 * Server-side proxy utilities for the Quart API backend.
 *
 * - Mints JWTs using the shared JWT_SECRET (same algo/payload as Python)
 * - Caches tokens in-memory per user email
 * - Provides proxyToBackend() and proxyStreamingToBackend()
 *
 * NOTE: This module runs ONLY on the Next.js server (API routes / RSC).
 *       No JWT is ever exposed to the browser.
 */
import "server-only";

import { SignJWT } from "jose";

import { auth } from "@/app/(auth)/auth";

// ── Config ──

function getApiBaseUrl(): string {
  const url =
    process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "";
  if (!url) throw new Error("API_BASE_URL / NEXT_PUBLIC_API_URL not set");
  return url.replace(/\/+$/, "");
}

export function isExternalBackend(): boolean {
  return Boolean(
    process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL
  );
}

// ── UUID5 (parity with Python uuid.uuid5(NAMESPACE_URL, "ari:user:{email}")) ──

const NAMESPACE_URL_BYTES = new Uint8Array([
  0x6b, 0xa7, 0xb8, 0x11, 0x9d, 0xad, 0x11, 0xd1, 0x80, 0xb4, 0x00, 0xc0,
  0x4f, 0xd4, 0x30, 0xc8,
]);

async function uuid5(name: string): Promise<string> {
  const encoder = new TextEncoder();
  const nameBytes = encoder.encode(name);
  const data = new Uint8Array(NAMESPACE_URL_BYTES.length + nameBytes.length);
  data.set(NAMESPACE_URL_BYTES);
  data.set(nameBytes, NAMESPACE_URL_BYTES.length);

  const hashBuffer = await crypto.subtle.digest("SHA-1", data);
  const hash = new Uint8Array(hashBuffer);

  // Set version 5
  hash[6] = (hash[6] & 0x0f) | 0x50;
  // Set variant RFC 4122
  hash[8] = (hash[8] & 0x3f) | 0x80;

  const hex = Array.from(hash.slice(0, 16))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

export async function deriveUserId(email: string): Promise<string> {
  return uuid5(`ari:user:${email}`);
}

// ── JWT cache ──

const jwtCache = new Map<string, { token: string; expiresAt: number }>();

async function mintJwt(email: string): Promise<string> {
  const secret = (process.env.JWT_SECRET || "").trim();
  if (!secret) {
    throw new Error(
      "JWT_SECRET is not set. Add JWT_SECRET to your .env file (must match apps/api JWT_SECRET)."
    );
  }

  const userId = await deriveUserId(email);
  const now = Math.floor(Date.now() / 1000);
  const exp = now + 86400; // 24 h

  const token = await new SignJWT({ sub: userId, email })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(now)
    .setExpirationTime(exp)
    .sign(new TextEncoder().encode(secret));

  jwtCache.set(email, { token, expiresAt: exp * 1000 });
  return token;
}

function getCachedJwt(email: string): string | null {
  const entry = jwtCache.get(email);
  if (!entry) return null;
  // Refresh 60 s before expiry
  if (entry.expiresAt < Date.now() + 60_000) return null;
  return entry.token;
}

/** Force-clear the cached JWT for a given email so the next call mints fresh. */
function invalidateJwt(email: string): void {
  jwtCache.delete(email);
}

export async function getAuthenticatedJwt(): Promise<string> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) throw new Error("Not authenticated");

  return getCachedJwt(email) ?? (await mintJwt(email));
}

/** Re-mint a fresh JWT (used after a 401 to retry). */
async function refreshJwt(): Promise<string> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) throw new Error("Not authenticated");
  invalidateJwt(email);
  return mintJwt(email);
}

/**
 * Check if the external backend is fully configured (URL + JWT_SECRET).
 * Returns null if OK, or an error Response if misconfigured.
 */
export function checkBackendConfig(): Response | null {
  if (!isExternalBackend()) {
    return Response.json(
      { error: "External backend not configured" },
      { status: 503 }
    );
  }
  const secret = (process.env.JWT_SECRET || "").trim();
  if (!secret) {
    console.error(
      "[api-proxy] JWT_SECRET is not set. Add it to .env (must match apps/api JWT_SECRET)."
    );
    return Response.json(
      { error: "Backend authentication not configured (JWT_SECRET missing)" },
      { status: 503 }
    );
  }
  return null;
}

// ── Proxy helpers ──

export async function proxyToBackend(
  path: string,
  opts: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
  } = {}
): Promise<Response> {
  const url = `${getApiBaseUrl()}${path}`;

  const doFetch = async (jwt: string) => {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${jwt}`,
      ...(opts.headers ?? {}),
    };

    let bodyStr: string | undefined;
    if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      bodyStr = JSON.stringify(opts.body);
    }

    return fetch(url, {
      method: opts.method ?? "GET",
      headers,
      body: bodyStr,
    });
  };

  let jwt = await getAuthenticatedJwt();
  let res = await doFetch(jwt);

  // Auto-retry once on 401: refresh JWT and retry
  if (res.status === 401) {
    jwt = await refreshJwt();
    res = await doFetch(jwt);
  }

  return res;
}

export async function proxyStreamingToBackend(
  path: string,
  body: unknown
): Promise<Response> {
  const url = `${getApiBaseUrl()}${path}`;
  const bodyStr = JSON.stringify(body);

  const doFetch = async (jwt: string) =>
    fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
        "Content-Type": "application/json",
      },
      body: bodyStr,
    });

  let jwt = await getAuthenticatedJwt();
  let upstream = await doFetch(jwt);

  // Auto-retry once on 401: refresh JWT and retry
  if (upstream.status === 401) {
    jwt = await refreshJwt();
    upstream = await doFetch(jwt);
  }

  if (!upstream.ok) {
    const text = await upstream.text();
    return new Response(text, { status: upstream.status });
  }

  if (!upstream.body) {
    return new Response("Empty upstream response", { status: 502 });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
