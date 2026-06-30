import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

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

test("renders a widget from streamed /state — one request, no /api/result", async () => {
  // Arrange
  const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
    Promise.resolve(streamResponse(PATCH_LINES)),
  );
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

  // Only the chat stream was requested — data arrived in-stream, not via /api/result
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/chat");
  const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
  expect(body.prompt).toBe("Revenue by month");
  expect(body.context.conversation_id).toBeTruthy();
});
