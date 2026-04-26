'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { usePresentation } from '@/contexts/PresentationContext';
import { MessageCircle, X, Send, ArrowRight } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function MessageContent({
  content,
  onNavigate,
}: {
  content: string;
  onNavigate: (slug: string) => void;
}) {
  const nodes: ReactNode[] = [];
  const re = /\[\[([^\]|]+)\|([^\]]+)\]\]/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = re.exec(content)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(<span key={key++}>{content.slice(lastIndex, match.index)}</span>);
    }
    const slug = match[1];
    const title = match[2];
    nodes.push(
      <button
        key={key++}
        onClick={() => onNavigate(slug)}
        className="inline-flex items-center gap-0.5 text-[#F7C35D] font-medium hover:opacity-75 transition-opacity cursor-pointer"
      >
        {title}
        <ArrowRight className="w-3 h-3 shrink-0" />
      </button>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    nodes.push(<span key={key++}>{content.slice(lastIndex)}</span>);
  }

  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{nodes}</p>
  );
}

export function AriChat() {
  const { courseSlug, navigateToSlug } = usePresentation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 'C' key toggles chat when not focused on an input
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 'c' || e.key === 'C') setOpen((o) => !o);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const history = messages;
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, courseSlug, history }),
      });

      if (!res.ok || !res.body) throw new Error('Request failed');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';

      setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        assistantContent += decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', content: assistantContent };
          return next;
        });
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, courseSlug]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const handleNavigate = useCallback(
    (slug: string) => {
      navigateToSlug(slug);
      setOpen(false);
    },
    [navigateToSlug]
  );

  return (
    <>
      {/* Chat panel */}
      {open && (
        <div className="fixed right-4 bottom-[88px] z-[80] w-[360px] max-w-[calc(100vw-2rem)] flex flex-col rounded-2xl border border-white/10 bg-[#0D0D0D] shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#111111]">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-[#F7C35D] flex items-center justify-center shrink-0">
                <span className="text-[10px] font-bold text-black leading-none">ARI</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-white leading-tight">ARI</p>
                <p className="text-[10px] text-white/40 leading-tight">Answers from this codex only</p>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded-lg hover:bg-white/5 text-white/40 hover:text-white/60 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[400px] min-h-[100px]">
            {messages.length === 0 && (
              <p className="text-xs text-white/25 text-center pt-6 leading-relaxed">
                Ask anything about this codex.
                <br />
                <span className="text-white/15">Press C to toggle · Enter to send</span>
              </p>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 ${
                    msg.role === 'user'
                      ? 'bg-[#F7C35D] text-black rounded-br-sm'
                      : 'bg-white/[0.06] text-white/90 rounded-bl-sm'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <MessageContent
                      content={msg.content || '…'}
                      onNavigate={handleNavigate}
                    />
                  ) : (
                    <p className="text-sm leading-relaxed">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            {loading && messages.at(-1)?.role === 'user' && (
              <div className="flex justify-start">
                <div className="bg-white/[0.06] rounded-2xl rounded-bl-sm px-3.5 py-2.5">
                  <span className="text-xs text-white/35 animate-pulse">ARI is thinking…</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-white/10 p-3 flex gap-2 items-end bg-[#111111]">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question…"
              rows={1}
              className="flex-1 resize-none bg-white/5 rounded-xl px-3 py-2 text-sm text-white/90 placeholder-white/25 outline-none focus:ring-1 focus:ring-[#F7C35D]/40 transition-shadow max-h-24 overflow-y-auto leading-relaxed"
            />
            <button
              onClick={send}
              disabled={!input.trim() || loading}
              className="p-2.5 rounded-xl bg-[#F7C35D] text-black hover:opacity-90 disabled:opacity-30 transition-opacity shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Floating button — hidden when panel is open */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          title="Ask ARI (C)"
          aria-label="Open ARI chat"
          className="fixed right-4 bottom-[88px] z-[80] w-12 h-12 rounded-full bg-[#F7C35D] text-black shadow-lg hover:opacity-90 active:scale-95 transition-all flex items-center justify-center"
        >
          <MessageCircle className="w-5 h-5" />
        </button>
      )}
    </>
  );
}
