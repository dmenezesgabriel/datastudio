import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// One stream: the narrative, a backend /state patch carrying the rows, and the
// LLM-authored DataTable bound to that widget's $state. No second request.
const PATCH_LINES = [
  '{"op":"add","path":"/root","value":"root"}',
  '{"op":"add","path":"/elements/root","value":{"type":"Stack","props":{},"children":[]}}',
  '{"op":"add","path":"/elements/narrative","value":{"type":"Markdown","props":{"text":"Two months of revenue."},"children":[]}}',
  '{"op":"add","path":"/elements/root/children/-","value":"narrative"}',
  '{"op":"add","path":"/state/widget-0","value":{"columns":["month","revenue"],"rows":[{"month":"Jan","revenue":100}]}}',
  '{"op":"add","path":"/elements/widget-0-table","value":{"type":"DataTable","props":{"data":{"$state":"/widget-0"}},"children":[]}}',
  '{"op":"add","path":"/elements/root/children/-","value":"widget-0-table"}',
];

function streamResponse(lines: string[]): Response {
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

// The sidebar's useConversations hook fetches /api/conversations on mount and after each
// turn. Route those to an empty JSON list so tests can focus on the /api/chat stream.
function jsonResponse(data: unknown): Response {
  return { ok: true, json: () => Promise.resolve(data) } as unknown as Response;
}

function routeFetch(chatResponder: () => Response) {
  return vi.fn((url: string, _init?: RequestInit) => {
    if (typeof url === "string" && url.startsWith("/api/conversations")) {
      return Promise.resolve(jsonResponse({ conversations: [] }));
    }
    return Promise.resolve(chatResponder());
  });
}

function chatCalls(mock: ReturnType<typeof routeFetch>) {
  return mock.mock.calls.filter((call) => call[0] === "/api/chat");
}

// A second turn's stream: a distinct narrative so the transcript is unambiguous.
const FOLLOW_UP_LINES = [
  '{"op":"add","path":"/root","value":"root"}',
  '{"op":"add","path":"/elements/root","value":{"type":"Stack","props":{},"children":[]}}',
  '{"op":"add","path":"/elements/narrative","value":{"type":"Markdown","props":{"text":"Broken down by week."},"children":[]}}',
  '{"op":"add","path":"/elements/root/children/-","value":"narrative"}',
];

test("renders a widget from streamed /state — one chat request, no /api/result", async () => {
  // Arrange
  const fetchMock = routeFetch(() => streamResponse(PATCH_LINES));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  // Act
  fireEvent.change(screen.getByPlaceholderText(/Ask a question/i), {
    target: { value: "Revenue by month" },
  });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  // Assert — narrative paints, and the table fills from the streamed $state data
  await waitFor(() => expect(screen.getByText(/Two months of revenue\./)).toBeTruthy());
  await waitFor(() => expect(screen.getByText("Jan")).toBeTruthy());
  expect(screen.getByText("100")).toBeTruthy();

  // Exactly one chat stream — data arrived in-stream, not via /api/result
  const calls = chatCalls(fetchMock);
  expect(calls).toHaveLength(1);
  expect(fetchMock.mock.calls.some((c) => c[0] === "/api/result")).toBe(false);
  const body = JSON.parse((calls[0][1] as RequestInit).body as string);
  expect(body.prompt).toBe("Revenue by month");
  expect(body.context.conversation_id).toBeTruthy();
});

// A grid widget the way the real serializer emits it: rows as /state, the DataTable leaf,
// the WidgetFrame wrapping it in the grid, and the SQL replaced onto the frame's prop.
const WIDGET_FRAME_LINES = [
  '{"op":"add","path":"/root","value":"root"}',
  '{"op":"add","path":"/elements/root","value":{"type":"Stack","props":{},"children":["narrative"]}}',
  '{"op":"add","path":"/elements/narrative","value":{"type":"Markdown","props":{"text":"Revenue by month."},"children":[]}}',
  '{"op":"add","path":"/elements/kpi-row","value":{"type":"KpiRow","props":{},"children":[]}}',
  '{"op":"add","path":"/elements/root/children/-","value":"kpi-row"}',
  '{"op":"add","path":"/elements/grid","value":{"type":"Grid","props":{},"children":[]}}',
  '{"op":"add","path":"/elements/root/children/-","value":"grid"}',
  '{"op":"add","path":"/state/widget-0","value":{"columns":["month","revenue"],"rows":[{"month":"Jan","revenue":100}]}}',
  '{"op":"add","path":"/elements/widget-0-table","value":{"type":"DataTable","props":{"data":{"$state":"/widget-0"}},"children":[]}}',
  '{"op":"add","path":"/elements/widget-0-frame","value":{"type":"WidgetFrame","props":{"sql":""},"children":["widget-0-table"]}}',
  '{"op":"add","path":"/elements/grid/children/-","value":"widget-0-frame"}',
  '{"op":"replace","path":"/elements/widget-0-frame/props/sql","value":"SELECT month, revenue FROM t"}',
];

test("renders a widget's Preview/SQL toggle and swaps its body to the SQL", async () => {
  // Arrange
  vi.stubGlobal("fetch", routeFetch(() => streamResponse(WIDGET_FRAME_LINES)));
  render(<App />);

  // Act — ask a question that streams a framed widget
  fireEvent.change(screen.getByPlaceholderText(/Ask a question/i), {
    target: { value: "Revenue by month" },
  });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  // Assert — Preview is the default: the widget's data shows; toggling reveals its SQL and
  // hides the data. This drives the real json-render Renderer + registry (WidgetFrame gets
  // both its `sql` prop and its rendered child), not the component in isolation.
  await waitFor(() => expect(screen.getByText("Jan")).toBeTruthy());
  fireEvent.click(screen.getByRole("button", { name: "SQL" }));
  expect(screen.getByText("SELECT month, revenue FROM t")).toBeTruthy();
  expect(screen.queryByText("Jan")).toBeNull();
});

// A stream that emits two progress patches, then stays open until `release()` is called,
// so the assertion runs while `isStreaming` is still true and the checklist is mounted.
// Progress rides the /state/progress key (json-render only applies /state + /elements).
const PROGRESS_LINES = [
  '{"op":"add","path":"/state/progress","value":{}}',
  '{"op":"add","path":"/state/progress/get_schema","value":{"label":"Reading the schema","status":"running","parentId":null,"order":0}}',
];

function heldStreamResponse(lines: string[]): { response: Response; release: () => void } {
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
  return { response: { ok: true, body: { getReader: () => reader } } as unknown as Response, release };
}

test("shows the live progress checklist while a turn is streaming", async () => {
  // Arrange — a stream held open after emitting a running progress step
  const held = heldStreamResponse(PROGRESS_LINES);
  vi.stubGlobal("fetch", routeFetch(() => held.response));
  render(<App />);

  // Act
  fireEvent.change(screen.getByPlaceholderText(/Ask a question/i), {
    target: { value: "Overview" },
  });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  // Assert — the checklist surfaces the streamed step while still streaming
  expect(await screen.findByText("Reading the schema")).toBeTruthy();
  expect(screen.getByText("◔")).toBeTruthy(); // running glyph

  // Cleanup — let the stream finish so no dangling promise leaks into other tests
  held.release();
  await waitFor(() => expect(screen.queryByText("Reading the schema")).toBeNull());
});

test("accumulates a transcript across turns on one stable conversation_id", async () => {
  // Arrange — each chat send gets its own stream; the follow-up carries a distinct narrative
  const streams = [PATCH_LINES, FOLLOW_UP_LINES];
  const fetchMock = routeFetch(() => streamResponse(streams.shift() ?? []));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  // Act — first question, then a follow-up
  fireEvent.change(screen.getByPlaceholderText(/Ask a question/i), {
    target: { value: "Revenue by month" },
  });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));
  await waitFor(() => expect(screen.getByText(/Two months of revenue\./)).toBeTruthy());

  fireEvent.change(screen.getByPlaceholderText(/Ask a question/i), {
    target: { value: "Break it down by week" },
  });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));
  await waitFor(() => expect(screen.getByText(/Broken down by week\./)).toBeTruthy());

  // Assert — the first turn is STILL on screen (transcript accumulated, not replaced),
  // and both questions are echoed as turns. Scope to the transcript (<main>) since the
  // sidebar also echoes the first question as the thread title.
  const transcript = within(screen.getByRole("main"));
  expect(transcript.getByText(/Two months of revenue\./)).toBeTruthy();
  expect(transcript.getByText("Revenue by month")).toBeTruthy();
  expect(transcript.getByText("Break it down by week")).toBeTruthy();

  // Both chat requests reused the same conversation_id (server-side memory key)
  const calls = chatCalls(fetchMock);
  expect(calls).toHaveLength(2);
  const cid = (call: number) =>
    JSON.parse((calls[call][1] as RequestInit).body as string).context.conversation_id;
  expect(cid(0)).toBe(cid(1));
});

test("reopening a past thread from the sidebar loads its transcript", async () => {
  // Arrange — the server lists one past thread and returns its transcript, including a
  // persisted DataTable bound to $state (a full dashboard, not just text).
  const detail = {
    turns: [
      {
        prompt: "Old question",
        spec: {
          root: "root",
          elements: {
            root: { type: "Stack", props: {}, children: ["narrative", "widget-0-table"] },
            narrative: { type: "Markdown", props: { text: "Past answer." }, children: [] },
            "widget-0-table": {
              type: "DataTable",
              props: { data: { $state: "/widget-0" } },
              children: [],
            },
          },
          state: { "widget-0": { columns: ["city", "orders"], rows: [{ city: "Sampa", orders: 42 }] } },
        },
      },
    ],
  };
  const fetchMock = vi.fn((url: string) => {
    if (url === "/api/conversations") {
      return Promise.resolve(
        jsonResponse({ conversations: [{ conversation_id: "past-1", title: "Old question" }] }),
      );
    }
    if (url === "/api/conversations/past-1") return Promise.resolve(jsonResponse(detail));
    return Promise.resolve(streamResponse([]));
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  // Act — click the past thread in the sidebar
  const threadButton = await screen.findByRole("button", { name: "Old question" });
  fireEvent.click(threadButton);

  // Assert — the reopened transcript renders its question, persisted answer, AND the
  // full dashboard (a table bound to persisted $state), not just text.
  await waitFor(() => expect(screen.getByText("Past answer.")).toBeTruthy());
  expect(within(screen.getByRole("main")).getByText("Old question")).toBeTruthy();
  expect(screen.getByText("Sampa")).toBeTruthy();
  expect(screen.getByText("42")).toBeTruthy();
});
