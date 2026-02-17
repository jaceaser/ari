"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface BillingProps {
  billing: {
    active: boolean;
    plan: string | null;
    status: string | null;
    expires_at: string | null;
  };
}

export function BillingClient({ billing }: BillingProps) {
  const [loading, setLoading] = useState(false);

  const handleSubscribe = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/billing/create-checkout", {
        method: "POST",
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-dvh w-screen items-start justify-center bg-background pt-12 md:items-center md:pt-0">
      <div className="flex w-full max-w-md flex-col gap-6 overflow-hidden rounded-2xl px-4 sm:px-16">
        <h2 className="text-center font-semibold text-2xl dark:text-zinc-50">
          Billing
        </h2>

        {billing.active ? (
          <div className="flex flex-col gap-3 rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-sm">Plan</span>
              <span className="font-medium text-sm">{billing.plan || "Active"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-sm">Status</span>
              <span className="font-medium text-sm capitalize">
                {billing.status || "active"}
              </span>
            </div>
            {billing.expires_at && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground text-sm">
                  Renews
                </span>
                <span className="font-medium text-sm">
                  {new Date(billing.expires_at).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4 text-center">
            <p className="text-muted-foreground text-sm">
              No active subscription. Subscribe to unlock full access.
            </p>
            <Button onClick={handleSubscribe} disabled={loading}>
              {loading ? "Redirecting..." : "Subscribe"}
            </Button>
          </div>
        )}

        <a
          href="/"
          className="text-center text-muted-foreground text-sm hover:underline"
        >
          Back to chat
        </a>
      </div>
    </div>
  );
}
