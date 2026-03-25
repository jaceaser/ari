import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { streamMessage, uploadFile, getMessages, Attachment } from '../lib/api';

export type ChatMessageItem = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  isError?: boolean;
  /** Local image URIs attached by the user (for display in bubble) */
  images?: string[];
  /** Document filenames attached by the user (for display in bubble) */
  docs?: string[];
};

function friendlyError(err: Error): string {
  const msg = err.message ?? '';
  if (
    msg.toLowerCase().includes('network') ||
    msg.toLowerCase().includes('fetch') ||
    msg.toLowerCase().includes('connect')
  ) {
    return "Couldn't connect to ARI. Check your internet connection.";
  }
  if (msg.includes('401') || msg.toLowerCase().includes('unauthorized')) {
    return 'Your session has expired. Please sign in again.';
  }
  if (
    msg.includes('429') ||
    msg.toLowerCase().includes('rate limit') ||
    msg.toLowerCase().includes('too many')
  ) {
    return 'Too many requests. Please wait a moment and try again.';
  }
  if (/[^1-4]5\d\d/.test(msg) || /^5\d\d/.test(msg) || msg.toLowerCase().includes('server error')) {
    return 'Something went wrong on our end. Please try again.';
  }
  return msg || 'Something went wrong. Please try again.';
}

export function useChatStream(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);
  const xhrAbortRef = useRef<(() => void) | null>(null);
  const lastInputRef = useRef<{ content: string; attachments: Attachment[] } | null>(null);
  const streamingRef = useRef(false);
  const bgDisconnectedRef = useRef(false);
  const bgFetchPendingRef = useRef(false);
  const sessionIdRef = useRef(sessionId);

  useEffect(() => { streamingRef.current = streaming; }, [streaming]);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);

  // When app backgrounds during streaming:
  //   - mark bgDisconnectedRef so the error handler keeps the partial response
  //   - mark bgFetchPendingRef so we refetch from server on foreground
  // When app returns to foreground:
  //   - wait 2s for server to finish saving, then load the complete response
  useEffect(() => {
    const sub = AppState.addEventListener('change', (nextState) => {
      if (nextState.match(/inactive|background/) && streamingRef.current) {
        bgDisconnectedRef.current = true;
        bgFetchPendingRef.current = true;
      } else if (nextState === 'active' && bgFetchPendingRef.current) {
        bgFetchPendingRef.current = false;
        setStreaming(false);
        // Give the server ~2s to finish generating and save to Cosmos DB,
        // then reload messages. Only apply if server has an assistant response.
        setTimeout(() => {
          getMessages(sessionIdRef.current)
            .then((msgs) => {
              if (!msgs?.length) return;
              const hasAssistant = msgs.some(
                (m) => m.role === 'assistant' && m.content?.trim(),
              );
              if (hasAssistant) loadMessages(msgs);
            })
            .catch(() => { /* silently ignore — user still has partial response */ });
        }, 2000);
      }
    });
    return () => sub.remove();
  }, [loadMessages]);

  const addUserMessage = useCallback((
    text: string,
    images?: string[],
    docs?: string[],
  ): string => {
    const id = `user-${Date.now()}`;
    setMessages((prev) => [...prev, { id, role: 'user', text, images, docs }]);
    return id;
  }, []);

  const sendMessage = useCallback(
    async (content: string, attachments: Attachment[] = []) => {
      if (streaming) return;
      setError(null);
      setStreaming(true);
      abortRef.current = false;
      lastInputRef.current = { content, attachments };

      const localImages = attachments.filter((a) => a.isImage).map((a) => a.uri);
      const localDocs = attachments.filter((a) => !a.isImage).map((a) => a.filename);
      addUserMessage(
        content,
        localImages.length ? localImages : undefined,
        localDocs.length ? localDocs : undefined,
      );

      // Upload any attachments before streaming
      const images: string[] = [];
      const documents: Array<{ url: string; mediaType: string }> = [];
      for (const a of attachments) {
        try {
          const result = await uploadFile(a.uri, a.mimeType, a.filename);
          if (a.isImage) {
            images.push(result.url);
          } else {
            documents.push({ url: result.url, mediaType: result.contentType });
          }
        } catch {
          // non-fatal: skip the attachment but continue with the message
        }
      }

      const assistantId = `asst-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', text: '' },
      ]);

      // Buffer chunks and flush at most every 32ms so the JS thread isn't
      // overwhelmed by a setMessages call on every single SSE token.
      const chunkBuffer = { current: '' };
      const flushTimer = { current: null as ReturnType<typeof setTimeout> | null };

      const flushBuffer = () => {
        flushTimer.current = null;
        const buffered = chunkBuffer.current;
        if (!buffered || abortRef.current) return;
        chunkBuffer.current = '';
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, text: m.text + buffered } : m,
          ),
        );
      };

      const { promise, abort } = streamMessage(
        sessionId,
        content,
        images.length ? images : undefined,
        documents.length ? documents : undefined,
        (chunk) => {
          if (abortRef.current) return;
          chunkBuffer.current += chunk;
          if (!flushTimer.current) {
            flushTimer.current = setTimeout(flushBuffer, 32);
          }
        },
        () => {
          // Flush any remaining buffered text before marking done
          if (flushTimer.current) { clearTimeout(flushTimer.current); }
          flushBuffer();
          xhrAbortRef.current = null;
          setStreaming(false);
        },
        (err) => {
          xhrAbortRef.current = null;
          setStreaming(false);
          if (bgDisconnectedRef.current) {
            // Stream was cut by app backgrounding — keep partial response, no error
            bgDisconnectedRef.current = false;
            return;
          }
          setError(err.message);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, text: friendlyError(err), isError: true }
                : m,
            ),
          );
        },
      );
      xhrAbortRef.current = abort;
      await promise;
    },
    [sessionId, streaming, addUserMessage],
  );

  const retry = useCallback(() => {
    const last = lastInputRef.current;
    if (!last || streaming) return;
    // Remove the error assistant bubble and the last user message, then resend
    setMessages((prev) => {
      const copy = [...prev];
      if (copy.length > 0 && copy[copy.length - 1].role === 'assistant' && copy[copy.length - 1].isError) {
        copy.pop();
      }
      if (copy.length > 0 && copy[copy.length - 1].role === 'user') {
        copy.pop();
      }
      return copy;
    });
    sendMessage(last.content, last.attachments);
  }, [streaming, sendMessage]);

  const loadMessages = useCallback(
    (loaded: Array<{ id: string; role: 'user' | 'assistant'; content: string }>) => {
      setMessages(
        loaded.map((m) => ({
          id: m.id,
          role: m.role,
          text: m.content ?? '',
        })),
      );
    },
    [],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current = true;
    xhrAbortRef.current?.();
    xhrAbortRef.current = null;
    setStreaming(false);
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, streaming, error, sendMessage, stopStreaming, retry, loadMessages, clearMessages };
}
