import { NextResponse } from "next/server";

import { auth } from "@/app/(auth)/auth";
import {
  getAuthenticatedJwt,
} from "@/lib/api-proxy";

const ALLOWED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
]);

const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export async function POST(request: Request) {
  const session = await auth();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (request.body === null) {
    return new Response("Request body is empty", { status: 400 });
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    if (!ALLOWED_TYPES.has(file.type)) {
      return NextResponse.json(
        { error: `File type not allowed: ${file.type}. Accepted: JPEG, PNG, WebP, GIF, PDF, Word` },
        { status: 400 },
      );
    }

    if (file.size > MAX_SIZE) {
      return NextResponse.json(
        { error: "File size should be less than 10MB" },
        { status: 400 },
      );
    }

    // Proxy upload to backend API (Azure Blob Storage)
    const apiBaseUrl = (
      process.env.API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      ""
    ).replace(/\/+$/, "");

    if (!apiBaseUrl) {
      return NextResponse.json(
        { error: "File upload not configured — backend API URL not set" },
        { status: 503 },
      );
    }

    let jwt: string;
    try {
      jwt = await getAuthenticatedJwt();
    } catch {
      return NextResponse.json({ error: "Authentication failed" }, { status: 401 });
    }

    // Forward the file as multipart form data to the backend
    const proxyForm = new FormData();
    proxyForm.append("file", file, file.name);

    const upstream = await fetch(`${apiBaseUrl}/documents/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${jwt}` },
      body: proxyForm,
    });

    const data = await upstream.json();

    if (!upstream.ok) {
      return NextResponse.json(
        { error: data.error || "Upload failed" },
        { status: upstream.status },
      );
    }

    return NextResponse.json(data);
  } catch (_error) {
    return NextResponse.json(
      { error: "Failed to process request" },
      { status: 500 },
    );
  }
}
