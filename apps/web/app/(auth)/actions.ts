"use server";

import { z } from "zod";

import { signIn } from "./auth";

const emailSchema = z.object({
  email: z.string().email(),
});

export type SendMagicLinkState = {
  status: "idle" | "in_progress" | "success" | "failed" | "invalid_data";
  message?: string;
};

export const sendMagicLink = async (
  _: SendMagicLinkState,
  formData: FormData
): Promise<SendMagicLinkState> => {
  try {
    const { email } = emailSchema.parse({
      email: formData.get("email"),
    });

    const apiUrl = (
      process.env.API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      ""
    ).replace(/\/+$/, "");

    if (!apiUrl) {
      return { status: "failed", message: "Backend not configured" };
    }

    const res = await fetch(`${apiUrl}/auth/magic-link/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    if (res.status === 429) {
      const data = await res.json().catch(() => ({}));
      return {
        status: "failed",
        message: data.detail || "Too many requests. Please wait and try again.",
      };
    }

    if (!res.ok) {
      return { status: "failed", message: "Failed to send magic link" };
    }

    return { status: "success" };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { status: "invalid_data" };
    }
    return { status: "failed" };
  }
};

export type VerifyMagicLinkState = {
  status: "idle" | "in_progress" | "success" | "failed";
};

export const verifyMagicLink = async (
  token: string
): Promise<VerifyMagicLinkState> => {
  try {
    await signIn("magic-link", {
      token,
      redirect: false,
    });

    return { status: "success" };
  } catch {
    return { status: "failed" };
  }
};
