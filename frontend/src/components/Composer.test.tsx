import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Composer } from "./Composer";

afterEach(cleanup);

test("keeps the draft after submit and clears it only on a success signal", () => {
  // A failed send used to wipe the typed question. The draft is now preserved until the
  // parent confirms success (a bumped clearSignal), so one retry re-sends it (audit MOD-3).
  const onSubmit = vi.fn();
  const { rerender } = render(<Composer onSubmit={onSubmit} disabled={false} clearSignal={0} />);
  const field = screen.getByRole("textbox") as HTMLTextAreaElement;

  fireEvent.change(field, { target: { value: "revenue by month" } });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));

  expect(onSubmit).toHaveBeenCalledWith("revenue by month");
  expect(field.value).toBe("revenue by month"); // preserved — not lost if the send failed

  rerender(<Composer onSubmit={onSubmit} disabled={false} clearSignal={1} />);
  expect(field.value).toBe(""); // success signal clears it
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
