"use client";

import { useActionState, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { AuthForm } from "@/components/auth-form";
import { SubmitButton } from "@/components/submit-button";
import { toast } from "@/components/toast";
import { type SendMagicLinkState, sendMagicLink } from "../actions";

export default function Page() {
  const [email, setEmail] = useState("");
  const t = useTranslations("auth");

  const [state, formAction] = useActionState<SendMagicLinkState, FormData>(
    sendMagicLink,
    { status: "idle" }
  );

  useEffect(() => {
    if (state.status === "failed") {
      toast({
        type: "error",
        description: state.message || t("errorGeneric"),
      });
    } else if (state.status === "invalid_data") {
      toast({
        type: "error",
        description: t("errorInvalidEmail"),
      });
    }
  }, [state.status, state.message, t]);

  const handleSubmit = (formData: FormData) => {
    setEmail(formData.get("email") as string);
    formAction(formData);
  };

  if (state.status === "success") {
    return (
      <div className="flex h-dvh w-screen items-start justify-center bg-background pt-12 md:items-center md:pt-0">
        <div className="flex w-full max-w-md flex-col gap-6 overflow-hidden rounded-2xl px-4 text-center sm:px-16">
          <h3 className="font-semibold text-xl dark:text-zinc-50">
            {t("checkEmail")}
          </h3>
          <p className="text-gray-500 text-sm dark:text-zinc-400">
            {t("sentLinkTo")}{" "}
            <span className="font-medium text-zinc-800 dark:text-zinc-200">
              {email}
            </span>
            . {t("clickLink")}
          </p>
          <p className="text-gray-400 text-xs dark:text-zinc-500">
            {t("linkExpires")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-dvh w-screen items-start justify-center bg-background pt-12 md:items-center md:pt-0">
      <div className="flex w-full max-w-md flex-col gap-12 overflow-hidden rounded-2xl">
        <div className="flex flex-col items-center justify-center gap-2 px-4 text-center sm:px-16">
          <h3 className="font-semibold text-xl dark:text-zinc-50">{t("signIn")}</h3>
          <p className="text-gray-500 text-sm dark:text-zinc-400">
            {t("enterEmail")}
          </p>
        </div>
        <AuthForm action={handleSubmit} defaultEmail={email}>
          <SubmitButton isSuccessful={false}>
            {t("sendLink")}
          </SubmitButton>
        </AuthForm>
      </div>
    </div>
  );
}
