import { auth } from "@/app/(auth)/auth";
import { proxyToBackend } from "@/lib/api-proxy";
import { redirect } from "next/navigation";
import { BillingClient } from "./billing-client";

export default async function BillingPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  let billing = { active: false, plan: null, status: null, expires_at: null };

  try {
    const res = await proxyToBackend("/billing/status");
    if (res.ok) {
      billing = await res.json();
    }
  } catch {
    // Fall through with defaults
  }

  return <BillingClient billing={billing} />;
}
