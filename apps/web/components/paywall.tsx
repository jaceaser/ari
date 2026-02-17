"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export function Paywall() {
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
    <div className="flex flex-col items-center gap-4 rounded-xl border bg-background p-8 text-center shadow-sm">
      <h3 className="font-semibold text-lg">Subscription Required</h3>
      <p className="max-w-sm text-muted-foreground text-sm">
        An active subscription is required to continue chatting. Subscribe to
        unlock unlimited access.
      </p>
      <Button onClick={handleSubscribe} disabled={loading}>
        {loading ? "Redirecting..." : "Subscribe to continue"}
      </Button>
    </div>
  );
}
