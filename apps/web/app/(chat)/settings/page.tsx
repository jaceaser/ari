"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { guestRegex } from "@/lib/constants";

export default function SettingsPage() {
  const { data: session, update } = useSession();
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const t = useTranslations("settings");

  const currentEmail = session?.user?.email ?? "";
  const isGuest = guestRegex.test(currentEmail);

  const handleEmailUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || trimmed === currentEmail) return;

    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch("/api/settings/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });

      if (res.ok) {
        setMessage({
          type: "success",
          text: t("emailUpdated"),
        });
        setEmail("");
        // Refresh the session to pick up the new email
        await update();
      } else {
        const data = await res.json().catch(() => ({}));
        setMessage({
          type: "error",
          text: data.error || t("errorUpdateEmail"),
        });
      }
    } catch {
      setMessage({ type: "error", text: t("errorNetwork") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col items-center justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

      <div className="flex w-full flex-col gap-4 rounded-lg border p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">{t("currentEmail")}</span>
          <span className="text-sm font-medium">
            {isGuest ? t("guestEmail") : currentEmail}
          </span>
        </div>

        {isGuest ? (
          <p className="text-sm text-muted-foreground">
            {t("guestNotice")}{" "}
            <Link className="underline" href="/login">
              {t("loginToSave")}
            </Link>{" "}
            {t("loginToSaveDesc")}
          </p>
        ) : (
          <form className="flex flex-col gap-3" onSubmit={handleEmailUpdate}>
            <label
              className="text-sm font-medium"
              htmlFor="new-email"
            >
              {t("changeEmail")}
            </label>
            <input
              autoComplete="email"
              className="rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              id="new-email"
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("emailPlaceholder")}
              type="email"
              value={email}
            />
            <Button disabled={saving || !email.trim()} type="submit">
              {saving ? t("updating") : t("updateEmail")}
            </Button>
          </form>
        )}

        {message && (
          <div
            className={`rounded-md px-4 py-3 text-sm ${
              message.type === "success"
                ? "bg-green-500/10 text-green-600"
                : "bg-red-500/10 text-red-600"
            }`}
          >
            {message.text}
          </div>
        )}
      </div>

      <Link
        className="text-sm text-muted-foreground underline"
        href="/"
      >
        {t("backToChat")}
      </Link>
    </div>
  );
}
