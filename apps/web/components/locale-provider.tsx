"use client";

import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import en from "@/messages/en.json";
import es from "@/messages/es.json";

const messagesMap: Record<string, AbstractIntlMessages> = { en, es };

function detectLocale(): string {
  // 1. Check cookie
  const match = document.cookie.match(/(?:^|;\s*)NEXT_LOCALE=([^;]+)/);
  if (match) {
    const val = match[1];
    if (val === "en" || val === "es") return val;
  }

  // 2. Check browser language
  const lang = navigator.language?.toLowerCase() ?? "";
  if (lang.startsWith("es")) return "es";

  return "en";
}

export function LocaleProvider({
  children,
  serverMessages,
}: {
  children: ReactNode;
  serverMessages: AbstractIntlMessages;
}) {
  const [locale, setLocale] = useState("en");
  const [messages, setMessages] = useState(serverMessages);

  useEffect(() => {
    const detected = detectLocale();
    if (detected !== "en") {
      setLocale(detected);
      setMessages(messagesMap[detected] ?? serverMessages);
    }
  }, [serverMessages]);

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
