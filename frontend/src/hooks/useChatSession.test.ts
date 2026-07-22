import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";

import { useChatSession } from "./useChatSession";
import {
  errorResponse,
  heldStreamResponse,
  jsonResponse,
  routeFetch,
  streamResponse,
} from "../test-support/streams";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ANSWER_LINES = [
  '{"op":"add","path":"/root","value":"root"}',
  '{"op":"add","path":"/elements/root","value":{"type":"Stack","props":{},"children":["narrative"]}}',
  '{"op":"add","path":"/elements/narrative","value":{"type":"Markdown","props":{"text":"Answer A."},"children":[]}}',
];

const PAST_DETAIL = {
  turns: [
    {
      prompt: "Old question",
      spec: {
        root: "root",
        elements: {
          root: { type: "Stack", props: {}, children: ["narrative"] },
          narrative: { type: "Markdown", props: { text: "Past answer." }, children: [] },
        },
        state: {},
      },
    },
  ],
};

function readyTurns(state: ReturnType<typeof useChatSession>["transcripts"][string]) {
  return state?.status === "ready" ? state.value : null;
}

// The URL is the source of truth for which conversation is on screen, so the user can
// navigate mid-stream (Back/Forward cannot be blocked). The session must therefore bind a
// question to the thread that asked it — not to whatever is showing when it finishes.
test("records a finished turn against the conversation that asked, not the one on screen", async () => {
  // Arrange — a stream held open so the test can navigate away before it completes.
  const held = heldStreamResponse(ANSWER_LINES);
  const fetchMock = vi.fn((url: string) => {
    if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
    if (url === "/api/conversations/conv-b") return Promise.resolve(jsonResponse(PAST_DETAIL));
    return Promise.resolve(held.response);
  });
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useChatSession());

  // Act — ask in A, then open B while A is still streaming, then let A finish.
  act(() => void result.current.ask("conv-a", "Question A"));
  await waitFor(() => expect(result.current.isStreaming).toBe(true));
  act(() => result.current.open("conv-b"));
  await waitFor(() => expect(readyTurns(result.current.transcripts["conv-b"])).toHaveLength(1));
  await act(async () => held.release());

  // Assert — A's answer landed in A, and never leaked into the thread being viewed.
  await waitFor(() => expect(readyTurns(result.current.transcripts["conv-a"])).toHaveLength(1));
  expect(readyTurns(result.current.transcripts["conv-a"])?.[0].prompt).toBe("Question A");
  expect(readyTurns(result.current.transcripts["conv-b"])).toHaveLength(1);
  expect(readyTurns(result.current.transcripts["conv-b"])?.[0].prompt).toBe("Old question");
});

test("names the conversation whose question is in flight so only that thread shows it", async () => {
  // Arrange
  const held = heldStreamResponse(ANSWER_LINES);
  vi.stubGlobal("fetch", routeFetch(() => held.response));
  const { result } = renderHook(() => useChatSession());

  // Act
  act(() => void result.current.ask("conv-a", "Question A"));

  // Assert — the stream is attributable, so a page showing another thread can ignore it.
  await waitFor(() => expect(result.current.isStreaming).toBe(true));
  expect(result.current.streamOwnerId).toBe("conv-a");
  expect(result.current.streamingPrompt).toBe("Question A");

  await act(async () => held.release());
});

test("mints a conversation id when asked without one", async () => {
  // A question typed at "/" has no server-side thread yet; the session mints its id so the
  // caller can put it in the URL.
  vi.stubGlobal("fetch", routeFetch(() => streamResponse(ANSWER_LINES)));
  const { result } = renderHook(() => useChatSession());

  let minted = "";
  act(() => {
    minted = result.current.ask(null, "First question");
  });

  expect(minted).toBeTruthy();
  await waitFor(() => expect(readyTurns(result.current.transcripts[minted])).toHaveLength(1));
});

test("does not fetch a just-created conversation the server has not saved yet", async () => {
  // Opening the URL we just navigated to must not hit /api/conversations/<new id> — the
  // turn is still streaming, so the server would 404 and the UI would claim it is missing.
  const held = heldStreamResponse(ANSWER_LINES);
  const fetchMock = routeFetch(() => held.response);
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useChatSession());

  let minted = "";
  act(() => {
    minted = result.current.ask(null, "First question");
  });
  act(() => result.current.open(minted));

  expect(result.current.transcripts[minted]?.status).toBe("ready");
  expect(fetchMock.mock.calls.some((call) => call[0] === `/api/conversations/${minted}`)).toBe(
    false,
  );

  await act(async () => held.release());
});

test("reports a 404 conversation as missing, not as an empty transcript", async () => {
  // Deep links outlive the in-memory store: a restarted backend 404s every saved id, and
  // "missing" is what lets the page say so instead of rendering a blank thread.
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
      return Promise.resolve(errorResponse(404));
    }),
  );
  const { result } = renderHook(() => useChatSession());

  act(() => result.current.open("gone"));

  await waitFor(() => expect(result.current.transcripts["gone"]?.status).toBe("missing"));
});

test("reports a failed load as retryable, and reload recovers it", async () => {
  // A 500/network blip is not a missing thread; re-requesting must be able to fix it.
  let detailCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
      detailCalls += 1;
      if (detailCalls === 1) return Promise.resolve(errorResponse(500));
      return Promise.resolve(jsonResponse(PAST_DETAIL));
    }),
  );
  const { result } = renderHook(() => useChatSession());

  act(() => result.current.open("past-1"));
  await waitFor(() => expect(result.current.transcripts["past-1"]?.status).toBe("error"));

  act(() => result.current.reload("past-1"));

  await waitFor(() => expect(readyTurns(result.current.transcripts["past-1"])).toHaveLength(1));
  expect(detailCalls).toBe(2);
});
