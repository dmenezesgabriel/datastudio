// App.tsx mints a conversation id at module load via crypto.randomUUID(); some
// jsdom builds lack it, so provide a deterministic stand-in for tests.
if (typeof globalThis.crypto?.randomUUID !== "function") {
  Object.defineProperty(globalThis, "crypto", {
    value: { ...globalThis.crypto, randomUUID: () => "test-conversation-id" },
    configurable: true,
  });
}
