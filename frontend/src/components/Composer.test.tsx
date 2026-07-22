import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Composer } from "./Composer";

afterEach(cleanup);

// Stands in for a browser that refuses to store anything — Safari's private mode and a full
// quota both throw from these calls rather than failing quietly.
class RefusingStorage implements Storage {
  readonly length = 0;
  getItem(): string | null {
    throw new DOMException("read denied", "SecurityError");
  }
  setItem(): void {
    throw new DOMException("quota exceeded", "QuotaExceededError");
  }
  removeItem(): void {
    throw new DOMException("write denied", "SecurityError");
  }
  clear(): void {}
  key(): string | null {
    return null;
  }
}

function installRefusingStorage() {
  const real = window.localStorage;
  Object.defineProperty(window, "localStorage", {
    value: new RefusingStorage(),
    configurable: true,
  });
  return () => Object.defineProperty(window, "localStorage", { value: real, configurable: true });
}

// jsdom lays nothing out, so every measurement reads 0 and the auto-grow effect has nothing
// to work with. Stand in for the browser: tests set `contentHeight` to what the draft "would"
// need (scrollHeight covers content + padding, never borders), plus whatever border the field
// itself carries — offsetHeight − clientHeight. That is zero now that the border belongs to
// .composer__box and not to the <textarea>; useAutoGrow still measures it rather than
// assuming, so a field that regains a border of its own stays correctly sized.
const BORDERS = 0;
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
  const { rerender } = render(<Composer onSubmit={onSubmit} disabled={false} draftKey="c-1" restoreSignal={0} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;

  fireEvent.change(field, { target: { value: "revenue by month" } });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  expect(onSubmit).toHaveBeenCalledWith("revenue by month");
  expect(field.value).toBe(""); // cleared optimistically on submit

  rerender(<Composer onSubmit={onSubmit} disabled={false} draftKey="c-1" restoreSignal={1} />);
  expect(field.value).toBe("revenue by month"); // a failed send restores it for retry
});

test("submits on Enter", () => {
  const onSubmit = vi.fn();
  render(<Composer onSubmit={onSubmit} disabled={false} draftKey="c-1" />);
  const field = screen.getByRole("textbox");

  fireEvent.change(field, { target: { value: "revenue by month" } });
  fireEvent.keyDown(field, { key: "Enter" });

  expect(onSubmit).toHaveBeenCalledWith("revenue by month");
});

test("does not submit on the Enter that confirms an IME candidate", () => {
  // Typing Japanese/Chinese/Korean, Enter accepts the candidate the IME is offering — it is
  // not a send. The browser says so via KeyboardEvent.isComposing; without this guard the
  // message goes out mid-word, which is why both claude.ai and ChatGPT guard every Enter
  // handler on the same flag.
  const onSubmit = vi.fn();
  render(<Composer onSubmit={onSubmit} disabled={false} draftKey="c-1" />);
  const field = screen.getByRole("textbox");

  fireEvent.change(field, { target: { value: "売上" } });
  fireEvent.keyDown(field, { key: "Enter", isComposing: true });

  expect(onSubmit).not.toHaveBeenCalled();
});

test("keeps an accessible name on the send button while it is busy", () => {
  // While streaming the visible label collapses to an ellipsis; the button must still be
  // named for assistive tech, not read as "…".
  render(<Composer onSubmit={vi.fn()} disabled draftKey="c-1" label="Ask" />);
  expect(screen.getByRole("button", { name: "Ask" })).toBeTruthy();
});

test("focuses the field on mount when asked to", () => {
  // A chat app should land the cursor in the composer so the user can type immediately.
  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" autoFocus />);
  expect(document.activeElement).toBe(screen.getByRole("textbox"));
});

test("does not steal focus when autoFocus is off", () => {
  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  expect(document.activeElement).not.toBe(screen.getByRole("textbox"));
});

test("gives the message field a name that survives the placeholder", () => {
  // A placeholder vanishes once the user types, leaving the field unnamed — so the textarea
  // carries a real accessible name of its own.
  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  expect(screen.getByRole("textbox", { name: /ask a question about your data/i })).toBeTruthy();
});

test("wraps the field and the send button in one bordered box", () => {
  // Both claude.ai and ChatGPT sit the send control inside the input surface rather than
  // beside it, so the whole composer reads as a single control. Asserted structurally
  // because that containment *is* the design — siblings in a row would look the same at
  // one width and come apart at another.
  const { container } = render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  const box = container.querySelector(".composer__box");

  expect(box).not.toBeNull();
  expect(box?.contains(screen.getByRole("textbox"))).toBe(true);
  expect(box?.contains(screen.getByRole("button", { name: /ask/i }))).toBe(true);
});

test("brings back a draft left unsent when the composer comes back", () => {
  // Half-written questions are expensive to retype. Navigating to a dashboard and back, or
  // reloading the tab, must not throw one away.
  const { unmount } = render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "revenue by month" } });
  unmount();

  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);

  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("revenue by month");
});

test("keeps each conversation's draft to itself", () => {
  const { unmount } = render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "revenue by month" } });
  unmount();

  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-2" />);

  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
});

test("swaps drafts when the composer is pointed at another conversation", () => {
  // The composer is not remounted when the user switches threads, so the hook itself has to
  // notice the key changed — otherwise thread B shows thread A's half-written question.
  const { rerender } = render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "revenue by month" } });

  rerender(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-2" />);
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");

  rerender(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("revenue by month");
});

test("forgets the draft once the question has been sent", () => {
  const { unmount } = render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "revenue by month" } });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));
  unmount();

  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);

  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
});

test("still composes and sends when the browser refuses to store drafts", () => {
  // Private-mode Safari and a full quota throw on every localStorage call. Losing draft
  // persistence there is acceptable; losing the ability to ask a question is not.
  const restore = installRefusingStorage();
  try {
    const onSubmit = vi.fn();
    render(<Composer onSubmit={onSubmit} disabled={false} draftKey="c-1" />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "revenue by month" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    expect(onSubmit).toHaveBeenCalledWith("revenue by month");
  } finally {
    restore();
  }
});

test("grows to fit the question being typed", () => {
  // A one-row field scrolls a long question out of its own view, and hides Shift+Enter
  // newlines entirely. The field takes the height its content needs.
  stubMeasuredHeight(0);
  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;

  stubMeasuredHeight(96);
  fireEvent.change(field, { target: { value: "line one\nline two\nline three\nline four" } });

  // 96 of content + padding, plus the borders scrollHeight leaves out — none of its own now
  // that .composer__box carries them, so the field is sized to its content exactly.
  expect(field.style.height).toBe("96px");
});

test("re-measures the draft when the field itself is resized", () => {
  // The height a draft needs depends on where its text wraps, so it is only valid at the
  // width it was measured at. Narrow the window (or open a phone keyboard) and a draft
  // measured wide re-wraps taller than the height it is stuck at, hiding its own last lines.
  stubMeasuredHeight(96);
  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "a four line draft at this width" } });

  stubMeasuredHeight(160); // the same text wraps to more lines in a narrower field
  resizeField();

  expect(field.style.height).toBe("160px");
});

test("shrinks back when the draft is cleared on submit", () => {
  // The measurement has to reset the height before reading scrollHeight — a field that only
  // ever grows would stay four rows tall over an empty draft.
  stubMeasuredHeight(96);
  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "line one\nline two\nline three\nline four" } });

  stubMeasuredHeight(32); // an empty field measures one row again
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  expect(field.style.height).toBe("32px");
});

test("re-measures the draft a failed send restores", () => {
  // The retry path (MOD-3) puts a multi-line question back into an emptied field; it has to
  // come back at its full height, not as one row with the rest scrolled away.
  stubMeasuredHeight(96);
  const { rerender } = render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" restoreSignal={0} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "line one\nline two\nline three\nline four" } });

  stubMeasuredHeight(32);
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  stubMeasuredHeight(96);
  rerender(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" restoreSignal={1} />);

  expect(field.style.height).toBe("96px");
});
