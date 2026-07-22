import { vi } from "vitest";

// Fetch stubs shared by the chat tests. The real `useUIStream` does the fetching, so tests
// drive it by stubbing `fetch` rather than mocking the hook — that keeps the streaming and
// patch-application paths under test instead of stubbed out.

/** A finished NDJSON patch stream that replays `lines` and closes. */
export function streamResponse(lines: string[]): Response {
  const encoder = new TextEncoder();
  let index = 0;
  const reader = {
    read(): Promise<ReadableStreamReadResult<Uint8Array>> {
      if (index < lines.length) {
        return Promise.resolve({ done: false, value: encoder.encode(lines[index++] + "\n") });
      }
      return Promise.resolve({ done: true, value: undefined });
    },
  };
  return { ok: true, body: { getReader: () => reader } } as unknown as Response;
}

/**
 * A patch stream that replays `lines` and then stays open until `release()` is called, so
 * assertions can run while `isStreaming` is still true.
 *
 * Example:
 *     const held = heldStreamResponse(PROGRESS_LINES);
 *     // …assert mid-stream…
 *     held.release();
 */
export function heldStreamResponse(lines: string[]): { response: Response; release: () => void } {
  const encoder = new TextEncoder();
  let index = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  const reader = {
    async read(): Promise<ReadableStreamReadResult<Uint8Array>> {
      if (index < lines.length) {
        return { done: false, value: encoder.encode(lines[index++] + "\n") };
      }
      await gate; // hold the stream open until the test releases it
      return { done: true, value: undefined };
    },
  };
  return {
    response: { ok: true, body: { getReader: () => reader } } as unknown as Response,
    release,
  };
}

/** A plain JSON response for the read-side endpoints (conversations, artifacts). */
export function jsonResponse(data: unknown): Response {
  return { ok: true, json: () => Promise.resolve(data) } as unknown as Response;
}

/** A failed response, so tests can distinguish a 404 (missing) from a 500 (retryable). */
export function errorResponse(status: number): Response {
  return { ok: false, status, json: () => Promise.resolve({ message: "boom" }) } as unknown as Response;
}

/**
 * A `fetch` stub that answers the sidebar/gallery reads with empty lists and routes
 * everything else to `chatResponder`, so a chat test only has to describe its stream.
 *
 * Example:
 *     vi.stubGlobal("fetch", routeFetch(() => streamResponse(PATCH_LINES)));
 */
export function routeFetch(chatResponder: () => Response) {
  return vi.fn((url: string, _init?: RequestInit) => {
    if (typeof url === "string" && url.startsWith("/api/conversations")) {
      return Promise.resolve(jsonResponse({ conversations: [] }));
    }
    if (typeof url === "string" && url.startsWith("/api/artifacts")) {
      return Promise.resolve(jsonResponse({ artifacts: [] }));
    }
    // The composer asks for the dataset's tables the moment it is focused, which is before
    // any question is sent. Answered here so that read never consumes the chat stream a
    // test queued up for its actual question.
    if (typeof url === "string" && url.startsWith("/api/schema/tables")) {
      return Promise.resolve(jsonResponse({ tables: [] }));
    }
    return Promise.resolve(chatResponder());
  });
}

/** The `/api/chat` calls made against a `routeFetch` stub, for asserting request bodies. */
export function chatCalls(mock: ReturnType<typeof routeFetch>) {
  return mock.mock.calls.filter((call) => call[0] === "/api/chat");
}

/** The `conversation_id` sent with the nth `/api/chat` request. */
export function sentConversationId(mock: ReturnType<typeof routeFetch>, index: number): string {
  const body = JSON.parse((chatCalls(mock)[index][1] as RequestInit).body as string);
  return body.context.conversation_id as string;
}
