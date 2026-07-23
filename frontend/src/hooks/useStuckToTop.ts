import { useCallback, useRef, useState } from "react";

/**
 * Track whether a `position: sticky` element is currently pinned to the top of its scroll
 * container, by observing a zero-height sentinel rendered just above it.
 *
 * A sticky element gives no DOM/CSS signal for its stuck state, so pinned-only styling (an
 * elevation shadow, squared bottom corners) needs this. Once the sentinel scrolls up and out
 * through the container's top edge, the sticky element below it has taken over that edge — i.e.
 * it is stuck. IntersectionObserver reports that crossing without a scroll listener (no jank).
 *
 * Returns a **callback ref** (not a ref object) so the observer is wired up the moment the
 * sentinel node attaches and torn down when it detaches — the sentinel often mounts on a later
 * render than the hook's first call (the bar renders nothing until its dimensions resolve), which
 * a `useEffect` keyed on a stable ref object would miss. The observer's root is the sentinel's
 * nearest scrollable ancestor, so it works in any dashboard scroll container (the artifact canvas
 * or the chat transcript) without being told which one.
 *
 * @returns `[stuck, sentinelRef]` — `stuck` is true while pinned; attach `sentinelRef` to a
 *   zero-height element placed immediately before the sticky element.
 *
 * @example
 *     const [stuck, sentinelRef] = useStuckToTop();
 *     return <><div ref={sentinelRef} /><header className={stuck ? "is-stuck" : ""} /></>;
 */
export function useStuckToTop(): [boolean, (node: HTMLElement | null) => void] {
  const [stuck, setStuck] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useCallback((node: HTMLElement | null) => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!node || typeof IntersectionObserver !== "function") return;
    const observer = new IntersectionObserver(
      ([entry]) => setStuck(!entry.isIntersecting),
      { root: nearestScrollParent(node), threshold: [0] },
    );
    observer.observe(node);
    observerRef.current = observer;
  }, []);
  return [stuck, sentinelRef];
}

/** The element's nearest ancestor that scrolls vertically, or null (the viewport) when none. */
function nearestScrollParent(element: HTMLElement): HTMLElement | null {
  for (let node = element.parentElement; node; node = node.parentElement) {
    const overflowY = getComputedStyle(node).overflowY;
    if (overflowY === "auto" || overflowY === "scroll") return node;
  }
  return null;
}
