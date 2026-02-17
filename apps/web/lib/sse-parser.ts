/**
 * Shared SSE parsing utilities for OpenAI-compatible streaming responses.
 *
 * Used by both the legacy /v1/chat/completions proxy and the new
 * /sessions/:id/messages proxy.
 */
import { generateId } from "ai";

export type OpenAIStreamChunk = {
  choices?: Array<{
    delta?: { content?: string };
    finish_reason?: string | null;
  }>;
  error?: { message?: string };
};

export type FinishReason =
  | "stop"
  | "length"
  | "content-filter"
  | "tool-calls"
  | "error"
  | "other"
  | undefined;

export function mapFinishReason(reason?: string | null): FinishReason {
  if (!reason) return undefined;
  if (reason === "stop") return "stop";
  if (reason === "length") return "length";
  if (reason === "content_filter") return "content-filter";
  if (reason === "tool_calls") return "tool-calls";
  return "other";
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Upstream streaming error";
}

export function splitSseEvent(
  buffer: string
): { event: string; rest: string } | null {
  const idxLf = buffer.indexOf("\n\n");
  const idxCrlf = buffer.indexOf("\r\n\r\n");

  if (idxLf === -1 && idxCrlf === -1) return null;

  if (idxCrlf !== -1 && (idxLf === -1 || idxCrlf < idxLf)) {
    return { event: buffer.slice(0, idxCrlf), rest: buffer.slice(idxCrlf + 4) };
  }

  return { event: buffer.slice(0, idxLf), rest: buffer.slice(idxLf + 2) };
}

export async function* parseOpenAISse(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<OpenAIStreamChunk, void, unknown> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    while (true) {
      const next = splitSseEvent(buffer);
      if (!next) break;
      buffer = next.rest;

      const dataLines = next.event
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart());

      if (dataLines.length === 0) continue;

      const data = dataLines.join("\n").trim();
      if (!data) continue;
      if (data === "[DONE]") return;

      try {
        yield JSON.parse(data) as OpenAIStreamChunk;
      } catch {
        // Ignore malformed chunks
      }
    }

    if (done) break;
  }
}

/**
 * Throttled text-delta writer: buffers incremental text and flushes at
 * a fixed interval to reduce the number of stream events reaching the
 * client. This smooths out rendering and avoids per-token re-renders.
 */
export const FLUSH_INTERVAL_MS = 50;

export class ThrottledDeltaWriter {
  private buffer = "";
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private writer: { write: (part: any) => void },
    private textId: string,
    private intervalMs = FLUSH_INTERVAL_MS
  ) {}

  /** Append text to the buffer. Starts the flush timer on first write. */
  push(delta: string): void {
    this.buffer += delta;
    if (!this.timer) {
      this.timer = setInterval(() => this.flush(), this.intervalMs);
    }
  }

  /** Flush buffered text to the writer. */
  flush(): void {
    if (this.buffer.length > 0) {
      this.writer.write({ type: "text-delta", id: this.textId, delta: this.buffer });
      this.buffer = "";
    }
  }

  /** Stop the timer and flush any remaining text. */
  finalize(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.flush();
  }
}

/**
 * Pipe an OpenAI-compatible SSE body into a UIMessageStream writer.
 *
 * Uses ThrottledDeltaWriter to batch text-delta events at FLUSH_INTERVAL_MS
 * intervals, reducing the number of writes reaching the client.
 * Skips tool_calls and meta-only chunks; deduplicates consecutive identical deltas.
 */
export async function writeOpenAiSseToUiStream(
  upstreamBody: ReadableStream<Uint8Array>,
  writer: {
    write: (part: any) => void;
  }
): Promise<void> {
  const textId = generateId();
  let finishReason: FinishReason;
  let lastDelta = "";
  const throttled = new ThrottledDeltaWriter(writer, textId);

  writer.write({ type: "start" });
  writer.write({ type: "start-step" });
  writer.write({ type: "text-start", id: textId });

  try {
    for await (const chunk of parseOpenAISse(upstreamBody)) {
      if (chunk.error?.message) {
        finishReason = "error";
        throttled.finalize();
        writer.write({ type: "error", errorText: chunk.error.message });
        break;
      }

      const choice = chunk.choices?.[0];
      if (!choice) continue;

      // Skip tool_calls-only chunks (no text content)
      const delta = choice.delta;
      if (!delta) continue;
      if ((delta as any).tool_calls && !delta.content) continue;

      const mappedReason = mapFinishReason(choice.finish_reason);
      if (mappedReason) {
        finishReason = mappedReason;
      }

      const text = delta.content;
      if (typeof text === "string" && text.length > 0) {
        // Deduplicate consecutive identical deltas
        if (text === lastDelta && text.length < 4) continue;
        lastDelta = text;
        throttled.push(text);
      }
    }
  } catch (error) {
    finishReason = "error";
    writer.write({ type: "error", errorText: getErrorMessage(error) });
  } finally {
    throttled.finalize();
    writer.write({ type: "text-end", id: textId });
    writer.write({ type: "finish-step" });
    writer.write({ type: "finish", finishReason });
  }
}
