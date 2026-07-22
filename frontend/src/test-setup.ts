import { afterEach } from "vitest";

// The composer parks unsent drafts in localStorage, which outlives React and is shared by
// every test in a file. Clearing it after each one keeps tests independent (F.I.R.S.T) —
// without this, a draft typed by one test reappears in the next composer that mounts.
afterEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    // A test may have swapped in a storage stand-in that refuses; nothing to reset.
  }
});

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

// ProseMirror reads geometry to place the caret and decide where a click landed; jsdom does
// no layout, so these are simply absent. Inert stand-ins let the editor mount and edit under
// test — anything that genuinely depends on measured positions belongs in a real browser.
const NO_BOX = { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 };
const emptyRectList = () => Object.assign([], { item: () => null }) as unknown as DOMRectList;

for (const proto of [Range.prototype, Element.prototype]) {
  if (typeof proto.getClientRects !== "function") proto.getClientRects = emptyRectList;
  if (typeof proto.getBoundingClientRect !== "function") {
    proto.getBoundingClientRect = () => ({ ...NO_BOX, toJSON: () => NO_BOX }) as DOMRect;
  }
}

// Nothing scrolls without layout either, so jsdom omits this outright. Present as an inert
// stand-in so components can ask; tests that care about *what* was scrolled spy on it.
if (typeof Element.prototype.scrollIntoView !== "function") {
  Element.prototype.scrollIntoView = () => {};
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
