import { useCallback, useEffect, useRef, useState } from "react";

/** Distance (px) from bottom to consider "at bottom". */
const AT_BOTTOM_THRESHOLD = 80;

/** Debounce interval for scroll state updates (ms). */
const SCROLL_DEBOUNCE_MS = 100;

export function useScrollToBottom() {
  const containerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const isAtBottomRef = useRef(true);
  const isUserScrollingRef = useRef(false);

  // Keep ref in sync with state
  useEffect(() => {
    isAtBottomRef.current = isAtBottom;
  }, [isAtBottom]);

  const checkIfAtBottom = useCallback(() => {
    if (!containerRef.current) {
      return true;
    }
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    return scrollTop + clientHeight >= scrollHeight - AT_BOTTOM_THRESHOLD;
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    if (!containerRef.current) {
      return;
    }
    containerRef.current.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior,
    });
  }, []);

  // Handle user scroll events — debounced state updates
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    let scrollTimeout: ReturnType<typeof setTimeout>;
    let stateTimeout: ReturnType<typeof setTimeout>;

    const handleScroll = () => {
      isUserScrollingRef.current = true;
      clearTimeout(scrollTimeout);
      clearTimeout(stateTimeout);

      // Debounce the React state update to avoid re-renders during fast scrolls
      const atBottom = checkIfAtBottom();
      isAtBottomRef.current = atBottom;

      stateTimeout = setTimeout(() => {
        setIsAtBottom(atBottom);
      }, SCROLL_DEBOUNCE_MS);

      // Reset user scrolling flag after scroll ends
      scrollTimeout = setTimeout(() => {
        isUserScrollingRef.current = false;
      }, 150);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
      clearTimeout(scrollTimeout);
      clearTimeout(stateTimeout);
    };
  }, [checkIfAtBottom]);

  // Auto-scroll when content changes — coalesced via RAF
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    let rafId: number | null = null;

    const scrollIfNeeded = () => {
      // Coalesce rapid mutations into a single RAF
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (isAtBottomRef.current && !isUserScrollingRef.current) {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: "instant",
          });
          isAtBottomRef.current = true;
          // Don't call setIsAtBottom here to avoid re-render during streaming
        }
      });
    };

    // Watch for DOM changes — skip characterData to reduce firing frequency;
    // childList + subtree already catch new nodes / Streamdown re-renders.
    const mutationObserver = new MutationObserver(scrollIfNeeded);
    mutationObserver.observe(container, {
      childList: true,
      subtree: true,
    });

    // Watch for size changes
    const resizeObserver = new ResizeObserver(scrollIfNeeded);
    resizeObserver.observe(container);

    // Also observe children for size changes
    for (const child of container.children) {
      resizeObserver.observe(child);
    }

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      mutationObserver.disconnect();
      resizeObserver.disconnect();
    };
  }, []);

  function onViewportEnter() {
    setIsAtBottom(true);
    isAtBottomRef.current = true;
  }

  function onViewportLeave() {
    setIsAtBottom(false);
    isAtBottomRef.current = false;
  }

  return {
    containerRef,
    endRef,
    isAtBottom,
    scrollToBottom,
    onViewportEnter,
    onViewportLeave,
  };
}
