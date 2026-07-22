// App.tsx mints a conversation id at module load via crypto.randomUUID(); some
// jsdom builds lack it, so provide a deterministic stand-in for tests.
if (typeof globalThis.crypto?.randomUUID !== "function") {
  Object.defineProperty(globalThis, "crypto", {
    value: { ...globalThis.crypto, randomUUID: () => "test-conversation-id" },
    configurable: true,
  });
}

// ChartJsView subscribes to prefers-color-scheme to re-theme charts; jsdom has no
// matchMedia, so provide an inert stand-in (no change events fire in tests).
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      onchange: null,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

// The Composer re-measures its field when the field's width changes; jsdom has no
// ResizeObserver, so provide an inert stand-in (it never fires). Composer.test.tsx swaps in
// its own that does, to drive that path.
if (typeof globalThis.ResizeObserver !== "function") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
