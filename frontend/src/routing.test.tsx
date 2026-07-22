import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";

import { renderAt } from "./test-support/render";
import { askQuestion } from "./test-support/composer";
import {
  errorResponse,
  heldStreamResponse,
  jsonResponse,
  routeFetch,
  streamResponse,
} from "./test-support/streams";

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

const PAST_LIST = { conversations: [{ conversation_id: "past-1", title: "Old question" }] };

const ARTIFACT_LIST = {
  artifacts: [{ artifact_id: "dash-1", title: "Revenue dashboard", updated_at: 0, version_count: 1 }],
};

const ARTIFACT_DETAIL = {
  artifact_id: "dash-1",
  title: "Revenue dashboard",
  current: 0,
  spec: {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["narrative"] },
      narrative: { type: "Markdown", props: { text: "Saved dashboard body." }, children: [] },
    },
    state: {},
  },
  versions: [{ index: 0, instruction: null, created_at: 0 }],
};

function pathname(): string {
  return screen.getByTestId("pathname").textContent ?? "";
}

test("a new chat lives at the root until it has been asked something", () => {
  vi.stubGlobal("fetch", routeFetch(() => streamResponse([])));
  renderAt("/");

  expect(pathname()).toBe("/");
  expect(screen.getByText(/What would you like to know\?/i)).toBeTruthy();
});

test("asking the first question moves the URL to that conversation, replacing the root", async () => {
  // Arrange
  vi.stubGlobal("fetch", routeFetch(() => streamResponse(ANSWER_LINES)));
  renderAt("/");

  // Act
  await askQuestion("Revenue by month");

  // Assert — the thread is now addressable…
  await waitFor(() => expect(pathname()).toMatch(/^\/chat\/.+/));
  expect(await screen.findByText("Answer A.")).toBeTruthy();
  // …and it REPLACED the root, so Back leaves the app instead of returning to a blank
  // duplicate of the chat the user is already looking at.
  expect(screen.getByTestId("navigation-type").textContent).toBe("REPLACE");
});

test("a deep link to a conversation loads its transcript with no interaction", async () => {
  // Arrange — only the list and detail endpoints; nothing is clicked.
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      if (url === "/api/conversations/past-1") return Promise.resolve(jsonResponse(PAST_DETAIL));
      return Promise.resolve(streamResponse([]));
    }),
  );

  // Act
  renderAt("/chat/past-1");

  // Assert
  expect(await screen.findByText("Past answer.")).toBeTruthy();
  expect(within(screen.getByRole("main")).getByText("Old question")).toBeTruthy();
});

test("selecting a thread in the sidebar puts it in the URL", async () => {
  // Arrange
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      if (url === "/api/conversations/past-1") return Promise.resolve(jsonResponse(PAST_DETAIL));
      return Promise.resolve(streamResponse([]));
    }),
  );
  renderAt("/");

  // Act
  fireEvent.click(await screen.findByRole("link", { name: "Old question" }));

  // Assert
  await waitFor(() => expect(pathname()).toBe("/chat/past-1"));
  expect(await screen.findByText("Past answer.")).toBeTruthy();
});

test("sidebar threads are real links, so they can be opened in a new tab", async () => {
  // A <button> cannot be middle-clicked, cmd-clicked, or copied as a URL — the whole point
  // of routing the threads is that each one is an address.
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      return Promise.resolve(streamResponse([]));
    }),
  );
  renderAt("/");

  const link = await screen.findByRole("link", { name: "Old question" });
  expect(link.getAttribute("href")).toBe("/chat/past-1");
});

test("the open thread is marked as the current page for assistive tech", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      if (url === "/api/conversations/past-1") return Promise.resolve(jsonResponse(PAST_DETAIL));
      return Promise.resolve(streamResponse([]));
    }),
  );
  renderAt("/chat/past-1");

  const link = await screen.findByRole("link", { name: "Old question" });
  expect(link.getAttribute("aria-current")).toBe("page");
});

test("a conversation the server does not have explains itself and offers a way out", async () => {
  // The transcript store is in-memory, so a restarted backend 404s every shared link.
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
      if (url.startsWith("/api/conversations/")) return Promise.resolve(errorResponse(404));
      return Promise.resolve(streamResponse([]));
    }),
  );

  renderAt("/chat/gone-forever");

  // `isn.t` rather than a literal apostrophe — the copy uses a typographic one.
  expect(await screen.findByText(/conversation isn.t available/i)).toBeTruthy();
  const home = screen.getByRole("link", { name: /start a new chat/i });
  expect(home.getAttribute("href")).toBe("/");
});

test("a failed transcript load can be retried from the page", async () => {
  // Arrange — the detail endpoint fails once, then succeeds.
  let detailCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      if (url === "/api/conversations/past-1") {
        detailCalls += 1;
        return Promise.resolve(detailCalls === 1 ? errorResponse(500) : jsonResponse(PAST_DETAIL));
      }
      return Promise.resolve(streamResponse([]));
    }),
  );
  renderAt("/chat/past-1");

  // Act — a transient failure is retryable, unlike a 404.
  fireEvent.click(await screen.findByRole("button", { name: /try again/i }));

  // Assert
  expect(await screen.findByText("Past answer.")).toBeTruthy();
  expect(detailCalls).toBe(2);
});

test("the gallery and one saved dashboard are each addressable", async () => {
  // Arrange
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
      if (url === "/api/artifacts") return Promise.resolve(jsonResponse(ARTIFACT_LIST));
      if (url === "/api/artifacts/dash-1") return Promise.resolve(jsonResponse(ARTIFACT_DETAIL));
      return Promise.resolve(streamResponse([]));
    }),
  );

  // Act — deep link straight to the gallery, then open a dashboard.
  renderAt("/artifacts");
  fireEvent.click(await screen.findByRole("link", { name: /open revenue dashboard/i }));

  // Assert
  await waitFor(() => expect(pathname()).toBe("/artifacts/dash-1"));
  expect(await screen.findByText("Saved dashboard body.")).toBeTruthy();
});

test("a deleted dashboard says so instead of painting a blank canvas", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse({ conversations: [] }));
      if (url === "/api/artifacts") return Promise.resolve(jsonResponse({ artifacts: [] }));
      return Promise.resolve(errorResponse(404));
    }),
  );

  renderAt("/artifacts/deleted");

  expect(await screen.findByText(/dashboard isn.t available/i)).toBeTruthy();
});

test("an unknown URL renders a not-found page rather than an empty shell", async () => {
  vi.stubGlobal("fetch", routeFetch(() => streamResponse([])));
  renderAt("/nope");

  expect(await screen.findByRole("heading", { name: /page not found/i })).toBeTruthy();
  expect(screen.getByRole("link", { name: /start a new chat/i }).getAttribute("href")).toBe("/");
});

test("a thread being answered elsewhere does not bleed into the thread on screen", async () => {
  // Arrange — ask in a new chat, then navigate to a past thread while it streams.
  const held = heldStreamResponse(ANSWER_LINES);
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/conversations") return Promise.resolve(jsonResponse(PAST_LIST));
      if (url === "/api/conversations/past-1") return Promise.resolve(jsonResponse(PAST_DETAIL));
      return Promise.resolve(held.response);
    }),
  );
  renderAt("/");

  // Act
  await askQuestion("Question A");
  await waitFor(() => expect(pathname()).toMatch(/^\/chat\/.+/));
  fireEvent.click(await screen.findByRole("link", { name: "Old question" }));
  await screen.findByText("Past answer.");

  // Assert — neither the in-flight question nor its answer is echoed into the thread we
  // navigated to. (Where the finished turn *does* land is covered in useChatSession.test.)
  const transcript = within(screen.getByRole("main"));
  expect(transcript.queryByText("Question A")).toBeNull();
  held.release();
  await waitFor(() => expect(within(screen.getByRole("main")).queryByText("Answer A.")).toBeNull());
});
