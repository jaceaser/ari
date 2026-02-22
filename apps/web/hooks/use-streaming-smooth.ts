import { useEffect, useRef, useState } from "react";

/**
 * Typewriter-style streaming text reveal — mimics ChatGPT.
 *
 * Strategy: **buffer first, reveal later** (like video streaming).
 *
 * 1. When streaming starts, wait until we have ≥ BUFFER_CHARS or
 *    BUFFER_MS has elapsed before revealing anything.
 * 2. Once the buffer threshold is met, reveal at a steady, fixed pace
 *    that's slightly slower than the average token arrival rate.
 * 3. The initial buffer acts as a shock absorber — the animation
 *    rarely catches up to the live text, so there are no pauses.
 * 4. When streaming ends, drain the remaining buffer at the same pace.
 *
 * The timer runs via a single setInterval with empty deps — it's
 * completely decoupled from React's render cycle and never restarts.
 */

/** Wait for this many chars before starting to reveal. */
const BUFFER_CHARS = 150;

/** Max time (ms) to wait for the buffer to fill before starting anyway. */
const BUFFER_MS = 600;

/** Chars revealed per tick once we start. */
const CHARS_PER_TICK = 12;

/** Tick interval in ms. 33ms ≈ 30 fps. */
const TICK_MS = 33;

export function useStreamingSmooth(
  text: string,
  isStreaming: boolean
): string {
  const didStreamRef = useRef(isStreaming);
  const targetRef = useRef(text);
  const isStreamingRef = useRef(isStreaming);
  const displayedLenRef = useRef(isStreaming ? 0 : text.length);
  const [displayed, setDisplayed] = useState(isStreaming ? "" : text);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountTimeRef = useRef(Date.now());
  const revealStartedRef = useRef(false);

  // Keep refs in sync every render
  targetRef.current = text;
  isStreamingRef.current = isStreaming;
  if (isStreaming) didStreamRef.current = true;

  // Single timer — starts on mount for streaming messages, never restarts
  useEffect(() => {
    if (!didStreamRef.current) return;

    const tick = () => {
      const target = targetRef.current;
      const cur = displayedLenRef.current;
      const streaming = isStreamingRef.current;

      // Phase 1: Buffering — wait for enough text before revealing
      if (!revealStartedRef.current) {
        const elapsed = Date.now() - mountTimeRef.current;
        const hasEnoughChars = target.length >= BUFFER_CHARS;
        const timedOut = elapsed >= BUFFER_MS;
        const streamDone = !streaming && target.length > 0;

        if (hasEnoughChars || timedOut || streamDone) {
          revealStartedRef.current = true;
        } else {
          return; // Keep waiting
        }
      }

      // Phase 2: Revealing at a steady pace
      if (cur >= target.length) {
        if (!streaming) {
          // All done — stop the timer
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
          setDisplayed(target);
        }
        return;
      }

      const newLen = Math.min(cur + CHARS_PER_TICK, target.length);
      displayedLenRef.current = newLen;
      setDisplayed(target.slice(0, newLen));
    };

    timerRef.current = setInterval(tick, TICK_MS);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []); // Empty deps — never restarts

  // Historical (non-streaming) messages — return full text, no animation
  if (!didStreamRef.current) return text;

  return displayed;
}
