import "server-only";

import { proxyToBackend } from "@/lib/api-proxy";
import { ChatSDKError } from "@/lib/errors";

/**
 * Check if the current user has an active subscription.
 * Returns null if billing is not enforced or user has an active sub,
 * or a 402 Response if subscription is required.
 */
export async function checkSubscription(): Promise<Response | null> {
  // Skip check if Stripe is not configured
  if (!process.env.STRIPE_PRICE_ID) {
    return null;
  }

  try {
    const res = await proxyToBackend("/billing/status");
    if (!res.ok) {
      // Backend error — don't block the user
      return null;
    }

    const data = await res.json();
    if (data.active) {
      return null;
    }

    return new ChatSDKError("payment_required:chat").toResponse();
  } catch {
    // On error, don't block the user
    return null;
  }
}
