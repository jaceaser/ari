"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
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
  const success = searchParams.get("success");
  const canceled = searchParams.get("canceled");
  const t = useTranslations("billing");

  useEffect(() => {
    fetch("/api/billing/status")
      .then((res) => res.json())
      .then(setBilling)
      .catch(() => setBilling(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col items-center justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

      {success && (
        <div className="rounded-md bg-green-500/10 px-4 py-3 text-sm text-green-600">
          {t("successMessage")}
        </div>
      )}

      {canceled && (
        <div className="rounded-md bg-yellow-500/10 px-4 py-3 text-sm text-yellow-600">
          {t("canceledMessage")}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">
          {t("loading")}
        </p>
      ) : billing?.active ? (
        <div className="flex w-full flex-col gap-4 rounded-lg border p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{t("status")}</span>
            <span className="rounded-full bg-green-500/10 px-3 py-1 text-sm font-medium text-green-600">
              {t("active")}
            </span>
          </div>
          {formatPlan(billing.tier, billing.plan) && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t("plan")}</span>
              <span className="text-sm font-medium">{formatPlan(billing.tier, billing.plan)}</span>
            </div>
          )}
          {billing.expires_at && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {t("nextBillingDate")}
              </span>
              <span className="text-sm font-medium">
                {new Date(billing.expires_at).toLocaleDateString()}
              </span>
            </div>
          )}
          <Button variant="outline" asChild>
            <a href="https://billing.stripe.com/p/login/aFa7sK4J91hJ5yVbxs5kk00" target="_blank" rel="noopener noreferrer">
              {t("manageSubscription")}
            </a>
          </Button>
          <p className="text-xs text-muted-foreground">
            {t("manageDesc")}
          </p>
        </div>
      ) : (
        <div className="flex w-full flex-col gap-4 rounded-lg border p-6">
          <p className="text-sm text-muted-foreground">
            {t("noSubscription")}
          </p>
          <Button
            size="lg"
            asChild
          >
            <a href="https://reilabs.ai/products/" target="_blank" rel="noopener noreferrer">
              {t("viewPlans")}
            </a>
          </Button>
        </div>
      )}

      <Link
        className="text-sm text-muted-foreground underline"
        href="/"
      >
        {t("backToChat")}
      </Link>
    </div>
  );
}
