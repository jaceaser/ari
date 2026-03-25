"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

type BillingStatus = {
  active: boolean;
  plan: string | null;
  tier: string | null;
  status: string | null;
  expires_at: string | null;
};

const TIER_LABELS: Record<string, string> = {
  elite: "ARI Elite",
  pro: "ARI Pro",
  basic: "ARI Basic",
  ari_elite: "ARI Elite",
  ari_pro: "ARI Pro",
  ari_lite: "ARI Basic",
};

function formatPlan(tier: string | null, plan: string | null): string | null {
  const key = (tier || plan || "").toLowerCase();
  return TIER_LABELS[key] ?? tier ?? plan ?? null;
}

export default function BillingPage() {
  const searchParams = useSearchParams();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);

  const success = searchParams.get("success");
  const canceled = searchParams.get("canceled");

  useEffect(() => {
    fetch("/api/billing/status")
      .then((res) => res.json())
      .then(setBilling)
      .catch(() => setBilling(null))
      .finally(() => setLoading(false));
  }, []);

  const handleManageSubscription = async () => {
    setPortalLoading(true);
    setPortalError(null);
    try {
      const res = await fetch("/api/billing/create-portal", {
        method: "POST",
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setPortalError(data.error ?? "Failed to open billing portal. Please try again.");
        setPortalLoading(false);
      }
    } catch {
      setPortalError("Failed to open billing portal. Please try again.");
      setPortalLoading(false);
    }
  };

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col items-center justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold">Billing</h1>

      {success && (
        <div className="rounded-md bg-green-500/10 px-4 py-3 text-sm text-green-600">
          Subscription activated successfully!
        </div>
      )}

      {canceled && (
        <div className="rounded-md bg-yellow-500/10 px-4 py-3 text-sm text-yellow-600">
          Checkout was canceled. You can try again when ready.
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">
          Loading billing info...
        </p>
      ) : billing?.active ? (
        <div className="flex w-full flex-col gap-4 rounded-lg border p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Status</span>
            <span className="rounded-full bg-green-500/10 px-3 py-1 text-sm font-medium text-green-600">
              Active
            </span>
          </div>
          {formatPlan(billing.tier, billing.plan) && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Plan</span>
              <span className="text-sm font-medium">{formatPlan(billing.tier, billing.plan)}</span>
            </div>
          )}
          {billing.expires_at && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Next billing date
              </span>
              <span className="text-sm font-medium">
                {new Date(billing.expires_at).toLocaleDateString()}
              </span>
            </div>
          )}
          <Button
            disabled={portalLoading}
            onClick={handleManageSubscription}
            variant="outline"
          >
            {portalLoading ? "Redirecting..." : "Manage Subscription"}
          </Button>
          {portalError && (
            <p className="text-xs text-red-500">{portalError}</p>
          )}
          <p className="text-xs text-muted-foreground">
            Change your plan, update payment method, or cancel.
          </p>
        </div>
      ) : (
        <div className="flex w-full flex-col gap-4 rounded-lg border p-6">
          <p className="text-sm text-muted-foreground">
            You don&apos;t have an active subscription. Subscribe to unlock full
            access.
          </p>
          <Button
            size="lg"
            asChild
          >
            <a href="https://reilabs.ai/products/" target="_blank" rel="noopener noreferrer">
              View Plans &amp; Subscribe
            </a>
          </Button>
        </div>
      )}

      <Link
        className="text-sm text-muted-foreground underline"
        href="/"
      >
        Back to chat
      </Link>
    </div>
  );
}
