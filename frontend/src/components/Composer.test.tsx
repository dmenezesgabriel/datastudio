import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Composer } from "./Composer";

afterEach(cleanup);

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
