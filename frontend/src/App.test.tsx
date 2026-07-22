import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";

import { renderAt } from "./test-support/render";
import {
  chatCalls,
  errorResponse,
  heldStreamResponse,
  jsonResponse,
  routeFetch,
  sentConversationId,
  streamResponse,
} from "./test-support/streams";

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

// A second turn's stream: a distinct narrative so the transcript is unambiguous.
const FOLLOW_UP_LINES = [
  '{"op":"add","path":"/root","value":"root"}',
  '{"op":"add","path":"/elements/root","value":{"type":"Stack","props":{},"children":[]}}',
  '{"op":"add","path":"/elements/narrative","value":{"type":"Markdown","props":{"text":"Broken down by week."},"children":[]}}',
  '{"op":"add","path":"/elements/root/children/-","value":"narrative"}',
];

function ask(question: string): void {
  fireEvent.change(screen.getByPlaceholderText(/Ask a question/i), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));
}

test("renders a widget from streamed /state — one chat request, no /api/result", async () => {
  // Arrange
  const fetchMock = routeFetch(() => streamResponse(PATCH_LINES));
  vi.stubGlobal("fetch", fetchMock);
  renderAt("/");

  // Act
  ask("Revenue by month");

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

test("renders a widget's SQL toggle and swaps its body to the SQL", async () => {
  // Arrange
  vi.stubGlobal("fetch", routeFetch(() => streamResponse(WIDGET_FRAME_LINES)));
  renderAt("/");

  // Act — ask a question that streams a framed widget
  ask("Revenue by month");

  // Assert — the widget is the default: its data shows; toggling reveals the SQL and
  // hides the data. This drives the real json-render Renderer + registry (WidgetFrame gets
  // both its `sql` prop and its rendered child), not the component in isolation.
  await waitFor(() => expect(screen.getByText("Jan")).toBeTruthy());
  fireEvent.click(screen.getByRole("button", { name: "Show SQL" }));
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

test("shows the live progress checklist while a turn is streaming", async () => {
  // Arrange — a stream held open after emitting a running progress step
  const held = heldStreamResponse(PROGRESS_LINES);
  vi.stubGlobal("fetch", routeFetch(() => held.response));
  renderAt("/");

  // Act
  ask("Overview");

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
  renderAt("/");

  // Act — first question, then a follow-up
  ask("Revenue by month");
  await waitFor(() => expect(screen.getByText(/Two months of revenue\./)).toBeTruthy());

  ask("Break it down by week");
  await waitFor(() => expect(screen.getByText(/Broken down by week\./)).toBeTruthy());

  // Assert — the first turn is STILL on screen (transcript accumulated, not replaced),
  // and both questions are echoed as turns. Scope to the transcript (<main>) since the
  // sidebar also echoes the first question as the thread title.
  const transcript = within(screen.getByRole("main"));
  expect(transcript.getByText(/Two months of revenue\./)).toBeTruthy();
  expect(transcript.getByText("Revenue by month")).toBeTruthy();
  expect(transcript.getByText("Break it down by week")).toBeTruthy();

  // Both chat requests reused the same conversation_id — the follow-up picked it up from
  // the URL the first question navigated to (server-side memory key).
  expect(chatCalls(fetchMock)).toHaveLength(2);
  expect(sentConversationId(fetchMock, 0)).toBe(sentConversationId(fetchMock, 1));
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
  renderAt("/");

  // Act — click the past thread in the sidebar
  fireEvent.click(await screen.findByRole("link", { name: "Old question" }));

  // Assert — the reopened transcript renders its question, persisted answer, AND the
  // full dashboard (a table bound to persisted $state), not just text.
  await waitFor(() => expect(screen.getByText("Past answer.")).toBeTruthy());
  expect(within(screen.getByRole("main")).getByText("Old question")).toBeTruthy();
  expect(screen.getByText("Sampa")).toBeTruthy();
  expect(screen.getByText("42")).toBeTruthy();
});

// A minimal persisted transcript (just a narrative) for the error test below.
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

const PAST_LIST = { conversations: [{ conversation_id: "past-1", title: "Old question" }] };

test("does not reuse the 'New chat' name for the unsaved active thread", () => {
  // Two controls sharing one accessible name is ambiguous; only the toolbar action is
  // "New chat", while the unsaved thread carries a distinct name.
  vi.stubGlobal("fetch", routeFetch(() => streamResponse([])));
  renderAt("/");
  expect(screen.getAllByRole("link", { name: "New chat" })).toHaveLength(1);
  expect(screen.getByRole("link", { name: /untitled chat/i })).toBeTruthy();
});

test("exposes a mobile navigation toggle wired to the sidebar", () => {
  // Arrange
  vi.stubGlobal("fetch", routeFetch(() => streamResponse([])));
  renderAt("/");

  // The menu button controls the sidebar (aria-controls → the nav's id) and reports state.
  const menu = screen.getByRole("button", { name: /navigation/i });
  const controls = menu.getAttribute("aria-controls");
  expect(controls).toBeTruthy();
  expect(document.getElementById(controls as string)).toBe(
    screen.getByRole("navigation", { name: /conversations/i }),
  );
  expect(menu.getAttribute("aria-expanded")).toBe("false");

  // Act — open the drawer
  fireEvent.click(menu);

  // Assert
  expect(menu.getAttribute("aria-expanded")).toBe("true");
});

test("closes the mobile drawer after choosing a destination", () => {
  // Arrange
  vi.stubGlobal("fetch", routeFetch(() => streamResponse([])));
  renderAt("/");
  const menu = screen.getByRole("button", { name: /navigation/i });
  fireEvent.click(menu);
  expect(menu.getAttribute("aria-expanded")).toBe("true");

  // Act — pick a destination (Artifacts) from the drawer
  fireEvent.click(screen.getByRole("link", { name: "Artifacts" }));

  // Assert — the drawer collapses so the choice isn't left hidden behind an open overlay
  expect(menu.getAttribute("aria-expanded")).toBe("false");
});

test("exposes a stream error as a role=alert live region so it is announced", async () => {
  // Arrange — a failing chat stream.
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
      if (url.startsWith("/api/artifacts")) return Promise.resolve(jsonResponse({ artifacts: [] }));
      return Promise.resolve(errorResponse(500));
    }),
  );
  renderAt("/");

  // Act — a failing prompt.
  ask("will fail");

  // Assert — the banner is a role=alert region (screen readers announce it), not a mute <p>.
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("boom");
});

test("a stream error stays with the thread that produced it when another is opened", async () => {
  // Arrange — the chat stream fails; the past thread loads fine.
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      if (url === "/api/conversations/past-1") return Promise.resolve(jsonResponse(PAST_DETAIL));
      return Promise.resolve(errorResponse(500));
    }),
  );
  renderAt("/");

  // Act — a failing prompt surfaces the error banner…
  ask("will fail");
  await waitFor(() => expect(screen.getByText("boom")).toBeTruthy());

  // …then opening another thread leaves it behind (the error belongs to the failed thread).
  fireEvent.click(await screen.findByRole("link", { name: "Old question" }));
  await waitFor(() => expect(screen.getByText("Past answer.")).toBeTruthy());
  expect(screen.queryByText("boom")).toBeNull();
});
