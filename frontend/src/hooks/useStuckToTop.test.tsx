import { afterEach, expect, test, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useStuckToTop } from "./useStuckToTop";

afterEach(() => vi.unstubAllGlobals());

// A controllable IntersectionObserver: captures the callback so a test can drive the sentinel
// in/out of view, and records observe/disconnect so we can assert the observer is torn down.
class FakeIntersectionObserver {
  static latest: FakeIntersectionObserver | null = null;
  observed: Element[] = [];
  disconnected = false;

  constructor(private readonly callback: IntersectionObserverCallback) {
    FakeIntersectionObserver.latest = this;
  }
  observe(element: Element) {
    this.observed.push(element);
  }
  unobserve() {}
  disconnect() {
    this.disconnected = true;
  }
  /** Simulate the sentinel crossing the container's top edge. */
  fire(isIntersecting: boolean) {
    const entry = { isIntersecting } as IntersectionObserverEntry;
    this.callback([entry], this as unknown as IntersectionObserver);
  }
}

function installFakeObserver(): void {
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver as unknown as typeof IntersectionObserver);
}

function fakeNode(): HTMLElement {
  const el = document.createElement("div");
  document.body.appendChild(el);
  return el;
}

test("wires the observer only once the sentinel node attaches, then tracks its crossing", () => {
  installFakeObserver();
  const { result } = renderHook(() => useStuckToTop());

  // Before the node attaches (the bar renders nothing until its dimensions resolve) there is no
  // observer yet — the regression a stable-ref useEffect missed.
  expect(FakeIntersectionObserver.latest).toBe(null);
  expect(result.current[0]).toBe(false);

  const node = fakeNode();
  act(() => result.current[1](node)); // sentinel mounts → callback ref fires
  const observer = FakeIntersectionObserver.latest!;
  expect(observer.observed).toContain(node);

  act(() => observer.fire(false)); // sentinel scrolled out of the top
  expect(result.current[0]).toBe(true);

  act(() => observer.fire(true)); // scrolled back to the top
  expect(result.current[0]).toBe(false);
});

test("disconnects the previous observer when the sentinel detaches", () => {
  installFakeObserver();
  const { result } = renderHook(() => useStuckToTop());

  act(() => result.current[1](fakeNode()));
  const observer = FakeIntersectionObserver.latest!;

  act(() => result.current[1](null)); // sentinel unmounts
  expect(observer.disconnected).toBe(true);
});
