import { useCallback, useRef, useState } from 'react';
import { streamMessage } from '../lib/api';

export type ChatMessageItem = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
};

export function useChatStream(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const addUserMessage = useCallback((text: string): string => {
    const id = `user-${Date.now()}`;
    setMessages((prev) => [...prev, { id, role: 'user', text }]);
    return id;
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (streaming) return;
      setError(null);
      abortRef.current = false;

      addUserMessage(content);

      const assistantId = `asst-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', text: '' },
      ]);
      setStreaming(true);

      await streamMessage(
        sessionId,
        content,
        (chunk) => {
          if (abortRef.current) return;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, text: m.text + chunk } : m,
            ),
          );
        },
        () => {
          setStreaming(false);
        },
        (err) => {
          setError(err.message);
          setStreaming(false);
          // Remove empty assistant placeholder on error
          setMessages((prev) =>
            prev.filter((m) => !(m.id === assistantId && m.text === '')),
          );
        },
      );
    },
    [sessionId, streaming, addUserMessage],
  );

  const loadMessages = useCallback(
    (loaded: Array<{ id: string; role: 'user' | 'assistant'; parts: Array<{ type: string; text?: string }> }>) => {
      setMessages(
        loaded.map((m) => ({
          id: m.id,
          role: m.role,
          text: m.parts.find((p) => p.type === 'text')?.text ?? '',
        })),
      );
    },
    [],
  );

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, streaming, error, sendMessage, loadMessages, clearMessages };
}
