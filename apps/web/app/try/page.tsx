"use client";

import { useEffect, useRef, useState } from "react";
import { Streamdown } from "streamdown";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://reilabs-ari-api.azurewebsites.net";

const MAX_QUESTIONS = 3;
const SIGNUP_URL = "https://reilabs.ai/getari";
const STORAGE_KEY = "ari_demo_token_v2";
const LEAD_KEY = "ari_demo_lead_v1";

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
  // Lead gate
  const [leadCaptured, setLeadCaptured] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadConsent, setLeadConsent] = useState(false);
  const [leadSubmitting, setLeadSubmitting] = useState(false);
  const [leadError, setLeadError] = useState("");

  // Chat
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
  const emailRef = useRef<HTMLInputElement>(null);

  // Restore lead + token from localStorage on mount
  useEffect(() => {
    const storedLead = localStorage.getItem(LEAD_KEY);
    if (storedLead) {
      setLeadCaptured(true);
    }

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

  // Focus email input when gate shows
  useEffect(() => {
    if (!leadCaptured) {
      setTimeout(() => emailRef.current?.focus(), 100);
    }
  }, [leadCaptured]);

  // Focus chat input after lead captured
  useEffect(() => {
    if (leadCaptured && tokenReady) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [leadCaptured, tokenReady]);

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

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  async function handleLeadSubmit(e: React.FormEvent) {
    e.preventDefault();
    const name = leadName.trim();
    const email = leadEmail.trim();
    if (!name || !email) return;

    setLeadSubmitting(true);
    setLeadError("");

    try {
      const res = await fetch(`${API_URL}/demo/lead`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, consent: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        setLeadError(data.error || "Something went wrong. Please try again.");
        return;
      }
      // Use server-issued token seeded with actual usage count for this email
      if (data.token) {
        setDemoToken(data.token);
        localStorage.setItem(STORAGE_KEY, data.token);
        const used = data.questionsUsed ?? 0;
        setQuestionsUsed(used);
        if (used >= MAX_QUESTIONS) setLimitReached(true);
      }
      localStorage.setItem(LEAD_KEY, JSON.stringify({ name, email, consent: true }));
      setLeadCaptured(true);
    } catch {
      setLeadError("Something went wrong. Please try again.");
    } finally {
      setLeadSubmitting(false);
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
            { role: "assistant", content: "Something went wrong. Please try again." },
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
        { role: "assistant", content: "Something went wrong. Please try again." },
      ]);
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  const questionsLeft = MAX_QUESTIONS - questionsUsed;

  return (
    <div className="flex flex-col h-dvh bg-background text-foreground font-sans">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b shrink-0">
        <div className="size-7 rounded-full bg-primary flex items-center justify-center">
          <span className="text-xs font-bold text-primary-foreground select-none">A</span>
        </div>
        <span className="font-semibold text-sm">ARI</span>
        <span className="text-xs text-muted-foreground ml-0.5">by REI Labs</span>
      </div>

      {/* Lead gate */}
      {!leadCaptured ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-8">
          <div className="w-full max-w-sm space-y-5">
            <div className="space-y-1 text-center">
              <p className="font-semibold text-base">Try ARI free</p>
              <p className="text-xs text-muted-foreground">
                Ask 3 real estate questions — no account needed.
              </p>
            </div>
            <form onSubmit={handleLeadSubmit} className="space-y-3">
              <input
                type="text"
                value={leadName}
                onChange={(e) => setLeadName(e.target.value)}
                placeholder="Your name"
                required
                maxLength={100}
                disabled={leadSubmitting}
                className="w-full rounded-xl border bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
              />
              <input
                ref={emailRef}
                type="email"
                value={leadEmail}
                onChange={(e) => setLeadEmail(e.target.value)}
                placeholder="Email address"
                required
                maxLength={200}
                disabled={leadSubmitting}
                className="w-full rounded-xl border bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
              />
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={leadConsent}
                  onChange={(e) => setLeadConsent(e.target.checked)}
                  disabled={leadSubmitting}
                  className="mt-0.5 size-4 shrink-0 accent-[hsl(41,92%,67%)] cursor-pointer"
                />
                <span className="text-xs text-muted-foreground leading-relaxed">
                  I agree to receive informational and marketing emails from REI
                  Labs. Consent is not a condition of purchase. You may
                  unsubscribe at any time. By checking this box, I agree to the{" "}
                  <a
                    href="https://reilabs.ai/privacy-policy"
                    target="_top"
                    rel="noopener noreferrer"
                    className="underline underline-offset-2 hover:text-foreground transition-colors"
                  >
                    Privacy Policy
                  </a>{" "}
                  and{" "}
                  <a
                    href="https://reilabs.ai/terms-of-service"
                    target="_top"
                    rel="noopener noreferrer"
                    className="underline underline-offset-2 hover:text-foreground transition-colors"
                  >
                    Terms of Service
                  </a>
                  .
                </span>
              </label>
              {leadError && (
                <p className="text-xs text-red-500">{leadError}</p>
              )}
              <button
                type="submit"
                disabled={!leadName.trim() || !leadEmail.trim() || !leadConsent || leadSubmitting}
                className="w-full bg-primary text-primary-foreground text-sm font-semibold py-2.5 rounded-xl hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                {leadSubmitting ? "Starting..." : "Start chatting →"}
              </button>
            </form>
          </div>
        </div>
      ) : (
        <>
          {/* Messages */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 min-h-0">
            {messages.length === 0 && tokenReady && (
              <div className="text-center text-sm text-muted-foreground mt-10 space-y-1">
                <p className="font-medium text-foreground">Ask ARI anything about real estate</p>
                <p className="text-xs">Leads · Comps · Strategy · Contracts</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground rounded-br-sm"
                      : "bg-muted text-foreground rounded-bl-sm prose prose-sm prose-neutral dark:prose-invert max-w-none"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    msg.content ? (
                      <Streamdown>{msg.content}</Streamdown>
                    ) : isStreaming && i === messages.length - 1 ? (
                      <span className="opacity-50">●●●</span>
                    ) : null
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Limit reached CTA */}
          {limitReached && (
            <div className="px-4 py-4 border-t bg-muted text-center space-y-2 shrink-0">
              <p className="text-sm font-medium">You&apos;ve used your 3 free questions</p>
              <p className="text-xs text-muted-foreground">
                Get full access to leads, comps, live data, and more.
              </p>
              <a
                href={SIGNUP_URL}
                target="_top"
                rel="noopener noreferrer"
                className="inline-block mt-1 bg-primary text-primary-foreground text-sm font-semibold px-5 py-2 rounded-xl hover:opacity-90 transition-opacity"
              >
                Get full access to ARI →
              </a>
            </div>
          )}

          {/* Input */}
          {!limitReached && (
            <form
              onSubmit={handleSubmit}
              className="flex gap-2 px-3 py-3 border-t shrink-0"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  tokenReady ? "Ask a real estate question..." : "Loading..."
                }
                disabled={isStreaming || !tokenReady}
                maxLength={500}
                className="flex-1 rounded-xl border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 min-w-0"
              />
              <button
                type="submit"
                disabled={!input.trim() || isStreaming || !tokenReady}
                className="bg-primary text-primary-foreground text-sm font-medium px-4 py-2 rounded-xl hover:opacity-90 transition-opacity disabled:opacity-40 shrink-0"
              >
                {isStreaming ? "..." : "Ask"}
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
