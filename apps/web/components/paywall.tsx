"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export function Paywall() {
  const [loading, setLoading] = useState(false);
  const t = useTranslations("paywall");

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
      <h3 className="font-semibold text-lg">{t("title")}</h3>
      <p className="max-w-sm text-muted-foreground text-sm">
        {t("desc")}
      </p>
      <Button onClick={handleSubscribe} disabled={loading}>
        {loading ? t("redirecting") : t("subscribe")}
      </Button>
    </div>
  );
}
