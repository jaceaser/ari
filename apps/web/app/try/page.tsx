"use client";

import { useEffect, useRef, useState } from "react";
import { Streamdown } from "streamdown";
import { useTranslations } from "next-intl";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://reilabs-ari-api.azurewebsites.net";

const MAX_QUESTIONS = 3;
const LOGIN_URL = "https://ari-web.azurewebsites.net/login";
const SIGNUP_URL = "https://reilabs.ai/getari";
const STORAGE_KEY = "ari_demo_token_v2";

interface Message {
  role: "user" | "assistant";
  content: string;
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

export default function TryPage() {
  const t = useTranslations("try");

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [demoToken, setDemoToken] = useState<string | null>(null);
  const [questionsUsed, setQuestionsUsed] = useState(0);
  const [limitReached, setLimitReached] = useState(false);
  const [tokenReady, setTokenReady] = useState(false);

  const pendingTokenRef = useRef<{ token: string; used: number } | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const hasStarted = messages.length > 0 || limitReached;

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const payload = decodeJwtPayload(stored);
      if (
        payload &&
        payload.sub === "demo" &&
        typeof payload.exp === "number" &&
        payload.exp > Date.now() / 1000
      ) {
        const q = typeof payload.q === "number" ? payload.q : 0;
        setDemoToken(stored);
        setQuestionsUsed(q);
        if (q >= MAX_QUESTIONS) setLimitReached(true);
        setTokenReady(true);
        return;
      }
    }
    fetchNewToken();
  }, []);

  useEffect(() => {
    if (tokenReady && !limitReached) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [tokenReady, limitReached]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  async function fetchNewToken() {
    try {
      const res = await fetch(`${API_URL}/demo/token`, { method: "POST" });
      const data = await res.json();
      setDemoToken(data.token);
      setQuestionsUsed(0);
      localStorage.setItem(STORAGE_KEY, data.token);
    } catch (err) {
      console.error("Failed to get demo token", err);
    } finally {
      setTokenReady(true);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || isStreaming || !demoToken || limitReached) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsStreaming(true);
    pendingTokenRef.current = null;

    try {
      const res = await fetch(`${API_URL}/demo/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${demoToken}`,
        },
        body: JSON.stringify({ content: userMsg }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 429 || data.error === "limit_reached") {
          setLimitReached(true);
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: "Something went wrong. Please try again.",
            },
          ]);
        }
        return;
      }

      const newToken = res.headers.get("X-Demo-Token");
      const qRemaining = res.headers.get("X-Questions-Remaining");
      if (newToken) {
        const remaining = parseInt(qRemaining ?? "0", 10);
        pendingTokenRef.current = {
          token: newToken,
          used: MAX_QUESTIONS - remaining,
        };
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") break;
          try {
            const parsed = JSON.parse(raw);
            const delta = parsed.choices?.[0]?.delta?.content;
            if (delta) {
              assistantText += delta;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  content: assistantText,
                };
                return updated;
              });
            }
          } catch {
            // ignore malformed chunk
          }
        }
      }

      if (assistantText.trim() && pendingTokenRef.current) {
        const { token, used } = pendingTokenRef.current;
        setDemoToken(token);
        localStorage.setItem(STORAGE_KEY, token);
        setQuestionsUsed(used);
        if (used >= MAX_QUESTIONS) setLimitReached(true);
      }
    } catch (err) {
      console.error("Demo chat error", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Something went wrong. Please try again.",
        },
      ]);
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  const questionsLeft = MAX_QUESTIONS - questionsUsed;

  return (
    <div
      className="relative flex flex-col h-dvh overflow-hidden font-sans"
      style={{ backgroundColor: "#080808", color: "#fff" }}
    >
      {/* Atmospheric glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 55% at 68% 15%, rgba(210,160,50,0.22) 0%, rgba(180,120,20,0.09) 40%, transparent 70%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 45% 55% at 25% 85%, rgba(255,190,70,0.07) 0%, transparent 60%)",
        }}
      />

      {/* Header */}
      <header className="relative z-10 flex items-center gap-2 px-4 py-3 shrink-0">
        <div
          className="size-6 rounded-full flex items-center justify-center shrink-0"
          style={{ backgroundColor: "hsl(41,92%,67%)" }}
        >
          <span className="text-xs font-bold text-black select-none">A</span>
        </div>
        <span className="font-semibold text-sm" style={{ color: "rgba(255,255,255,0.9)" }}>
          ARI
        </span>
        <span className="text-xs ml-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>
          by REI Labs
        </span>
        {!hasStarted && tokenReady && questionsLeft > 0 && (
          <span
            className="ml-auto text-xs tabular-nums"
            style={{ color: "rgba(255,255,255,0.25)" }}
          >
            {questionsLeft} free question{questionsLeft !== 1 ? "s" : ""}
          </span>
        )}
      </header>

      {/* ── HERO STATE ── */}
      {!hasStarted && (
        <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 pb-10">
          <div
            aria-hidden
            className="absolute inset-0 flex items-center justify-center pointer-events-none select-none"
          >
            <span
              style={{
                fontSize: "clamp(96px, 22vw, 220px)",
                fontWeight: 900,
                letterSpacing: "-0.04em",
                lineHeight: 1,
                color: "transparent",
                WebkitTextStroke: "1px rgba(255,255,255,0.055)",
                textShadow: "0 0 120px rgba(210,160,50,0.12)",
              }}
            >
              ARI
            </span>
          </div>

          <p
            className="text-sm mb-8 z-10 relative"
            style={{ color: "rgba(255,255,255,0.38)" }}
          >
            Ask anything about real estate
          </p>

          <form onSubmit={handleSubmit} className="w-full max-w-lg z-10 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="What do you want to know?"
              disabled={isStreaming || !tokenReady}
              maxLength={500}
              className="w-full rounded-2xl px-5 py-4 text-sm pr-14 focus:outline-none disabled:opacity-50"
              style={{
                backgroundColor: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#fff",
                caretColor: "hsl(41,92%,67%)",
              }}
              onFocus={(e) =>
                (e.currentTarget.style.boxShadow = "0 0 0 1px rgba(210,160,50,0.4)")
              }
              onBlur={(e) => (e.currentTarget.style.boxShadow = "none")}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming || !tokenReady}
              aria-label="Ask"
              className="absolute right-3 top-1/2 -translate-y-1/2 size-8 rounded-full flex items-center justify-center transition-opacity disabled:opacity-25 hover:opacity-85"
              style={{ backgroundColor: "hsl(41,92%,67%)", color: "#000" }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M1 7h12M7 1l6 6-6 6"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </form>

          <p
            className="text-xs mt-4 z-10 relative"
            style={{ color: "rgba(255,255,255,0.18)" }}
          >
            No account needed &middot; {MAX_QUESTIONS} questions free
          </p>
        </div>
      )}

      {/* ── CHAT STATE ── */}
      {hasStarted && (
        <>
          <div
            ref={scrollContainerRef}
            className="relative z-10 flex-1 overflow-y-auto px-4 py-4 space-y-3 min-h-0"
          >
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    msg.role === "assistant"
                      ? "prose prose-sm prose-invert max-w-none rounded-bl-sm"
                      : "rounded-br-sm font-medium"
                  }`}
                  style={
                    msg.role === "user"
                      ? { backgroundColor: "hsl(41,92%,67%)", color: "#000" }
                      : { backgroundColor: "rgba(255,255,255,0.07)", color: "rgba(255,255,255,0.88)" }
                  }
                >
                  {msg.role === "assistant" ? (
                    msg.content ? (
                      <Streamdown>{msg.content}</Streamdown>
                    ) : isStreaming && i === messages.length - 1 ? (
                      <span style={{ opacity: 0.35 }}>...</span>
                    ) : null
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Limit reached — Grok-style bar */}
          {limitReached && (
            <div className="relative z-10 px-4 py-3 shrink-0">
              <div
                className="flex items-center gap-3 rounded-2xl px-4 py-3"
                style={{ backgroundColor: "rgba(255,255,255,0.08)" }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  className="shrink-0"
                  style={{ color: "rgba(255,255,255,0.6)" }}
                >
                  <path
                    d="M8 1.5L1 14h14L8 1.5z"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinejoin="round"
                  />
                  <path d="M8 6v4M8 11.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold leading-tight">
                    {t("usedFreeQuestions")}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.45)" }}>
                    Sign up for free to continue using ARI
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <a
                    href={LOGIN_URL}
                    target="_top"
                    rel="noopener noreferrer"
                    className="text-sm font-semibold px-4 py-1.5 rounded-full transition-opacity hover:opacity-80"
                    style={{
                      border: "1px solid rgba(255,255,255,0.25)",
                      color: "#fff",
                    }}
                  >
                    Log in
                  </a>
                  <a
                    href={SIGNUP_URL}
                    target="_top"
                    rel="noopener noreferrer"
                    className="text-sm font-semibold px-4 py-1.5 rounded-full transition-opacity hover:opacity-90"
                    style={{
                      backgroundColor: "#fff",
                      color: "#000",
                    }}
                  >
                    Sign up
                  </a>
                </div>
              </div>
            </div>
          )}

          {/* Chat input */}
          {!limitReached && (
            <form
              onSubmit={handleSubmit}
              className="relative z-10 flex gap-2 px-3 py-3 shrink-0"
              style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={tokenReady ? t("messagePlaceholder") : t("starting")}
                disabled={isStreaming || !tokenReady}
                maxLength={500}
                className="flex-1 rounded-xl px-3 py-2.5 text-sm focus:outline-none disabled:opacity-50 min-w-0"
                style={{
                  backgroundColor: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#fff",
                  caretColor: "hsl(41,92%,67%)",
                }}
              />
              <button
                type="submit"
                disabled={!input.trim() || isStreaming || !tokenReady}
                className="text-sm font-medium px-4 py-2 rounded-xl transition-opacity hover:opacity-90 disabled:opacity-35 shrink-0"
                style={{ backgroundColor: "hsl(41,92%,67%)", color: "#000" }}
              >
                {isStreaming ? "..." : t("ask")}
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
