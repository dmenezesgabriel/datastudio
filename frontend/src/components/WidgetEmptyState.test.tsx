import { afterEach, expect, test } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { WidgetEmptyState } from "./WidgetEmptyState";

afterEach(cleanup);

test("tells the user no rows match, and how to recover", () => {
  render(<WidgetEmptyState />);
  const note = screen.getByRole("status");
  expect(note.textContent).toMatch(/no rows match/i);
  expect(note.textContent).toMatch(/filter/i);
});
