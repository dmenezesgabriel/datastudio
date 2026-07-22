import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Composer } from "./Composer";

afterEach(cleanup);

// jsdom lays nothing out, so every measurement reads 0 and the auto-grow effect has nothing
// to work with. Stand in for the browser: tests set `contentHeight` to what the draft "would"
// need (scrollHeight covers content + padding, never borders), and the field carries the
// 1px border top and bottom the composer styles give it — offsetHeight − clientHeight.
const BORDERS = 2;
let contentHeight = 0;

function stubMeasuredHeight(height: number) {
  contentHeight = height;
  stubMetric("scrollHeight", () => contentHeight);
  stubMetric("offsetHeight", () => BORDERS);
  stubMetric("clientHeight", () => 0);
}

function stubMetric(name: string, get: () => number) {
  Object.defineProperty(HTMLTextAreaElement.prototype, name, { configurable: true, get });
}

// Deleting the own properties restores the inherited jsdom accessors for the next test.
afterEach(() => {
  for (const name of ["scrollHeight", "offsetHeight", "clientHeight"]) {
    Reflect.deleteProperty(HTMLTextAreaElement.prototype, name);
  }
});

// jsdom never resizes anything, so stand in for the browser's ResizeObserver: `resizeField`
// fires whatever the component observed with.
let resizeField = () => {};

beforeEach(() => {
  globalThis.ResizeObserver = class {
    constructor(onResize: ResizeObserverCallback) {
      resizeField = () => act(() => onResize([], this));
    }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

test("clears the draft on submit and restores it when the send fails", () => {
  // The field clears optimistically on submit (as chat inputs do); a failed send bumps
  // restoreSignal to put the question back so one retry re-sends it (audit MOD-3).
  const onSubmit = vi.fn();
  const { rerender } = render(<Composer onSubmit={onSubmit} disabled={false} restoreSignal={0} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;

  fireEvent.change(field, { target: { value: "revenue by month" } });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  expect(onSubmit).toHaveBeenCalledWith("revenue by month");
  expect(field.value).toBe(""); // cleared optimistically on submit

  rerender(<Composer onSubmit={onSubmit} disabled={false} restoreSignal={1} />);
  expect(field.value).toBe("revenue by month"); // a failed send restores it for retry
});

test("keeps an accessible name on the send button while it is busy", () => {
  // While streaming the visible label collapses to an ellipsis; the button must still be
  // named for assistive tech, not read as "…".
  render(<Composer onSubmit={vi.fn()} disabled label="Ask" />);
  expect(screen.getByRole("button", { name: "Ask" })).toBeTruthy();
});

test("focuses the field on mount when asked to", () => {
  // A chat app should land the cursor in the composer so the user can type immediately.
  render(<Composer onSubmit={vi.fn()} disabled={false} autoFocus />);
  expect(document.activeElement).toBe(screen.getByRole("textbox"));
});

test("does not steal focus when autoFocus is off", () => {
  render(<Composer onSubmit={vi.fn()} disabled={false} />);
  expect(document.activeElement).not.toBe(screen.getByRole("textbox"));
});

test("gives the message field a name that survives the placeholder", () => {
  // A placeholder vanishes once the user types, leaving the field unnamed — so the textarea
  // carries a real accessible name of its own.
  render(<Composer onSubmit={vi.fn()} disabled={false} />);
  expect(screen.getByRole("textbox", { name: /ask a question about your data/i })).toBeTruthy();
});

test("grows to fit the question being typed", () => {
  // A one-row field scrolls a long question out of its own view, and hides Shift+Enter
  // newlines entirely. The field takes the height its content needs.
  stubMeasuredHeight(0);
  render(<Composer onSubmit={vi.fn()} disabled={false} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;

  stubMeasuredHeight(96);
  fireEvent.change(field, { target: { value: "line one\nline two\nline three\nline four" } });

  // 96 of content + padding, plus the borders scrollHeight leaves out — a field sized to
  // scrollHeight alone is 2px short of its own text and scrolls at every height.
  expect(field.style.height).toBe("98px");
});

test("re-measures the draft when the field itself is resized", () => {
  // The height a draft needs depends on where its text wraps, so it is only valid at the
  // width it was measured at. Narrow the window (or open a phone keyboard) and a draft
  // measured wide re-wraps taller than the height it is stuck at, hiding its own last lines.
  stubMeasuredHeight(96);
  render(<Composer onSubmit={vi.fn()} disabled={false} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "a four line draft at this width" } });

  stubMeasuredHeight(160); // the same text wraps to more lines in a narrower field
  resizeField();

  expect(field.style.height).toBe("162px");
});

test("shrinks back when the draft is cleared on submit", () => {
  // The measurement has to reset the height before reading scrollHeight — a field that only
  // ever grows would stay four rows tall over an empty draft.
  stubMeasuredHeight(96);
  render(<Composer onSubmit={vi.fn()} disabled={false} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "line one\nline two\nline three\nline four" } });

  stubMeasuredHeight(32); // an empty field measures one row again
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  expect(field.style.height).toBe("34px");
});

test("re-measures the draft a failed send restores", () => {
  // The retry path (MOD-3) puts a multi-line question back into an emptied field; it has to
  // come back at its full height, not as one row with the rest scrolled away.
  stubMeasuredHeight(96);
  const { rerender } = render(<Composer onSubmit={vi.fn()} disabled={false} restoreSignal={0} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "line one\nline two\nline three\nline four" } });

  stubMeasuredHeight(32);
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  stubMeasuredHeight(96);
  rerender(<Composer onSubmit={vi.fn()} disabled={false} restoreSignal={1} />);

  expect(field.style.height).toBe("98px");
});
