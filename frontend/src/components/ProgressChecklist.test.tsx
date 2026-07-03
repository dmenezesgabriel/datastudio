import { afterEach, describe, expect, test } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import { ProgressChecklist } from "./ProgressChecklist";
import type { ProgressSteps } from "../types";

afterEach(cleanup);

describe("ProgressChecklist", () => {
  test("renders nothing when there are no steps", () => {
    // Arrange / Act
    const { container } = render(<ProgressChecklist steps={undefined} />);
    // Assert
    expect(container.firstChild).toBeNull();
  });

  test("renders steps in order, nesting a widget's sub-step under its parent", () => {
    // Arrange — a top-level step, a widget parent, and its child, out of insertion order
    const steps: ProgressSteps = {
      "widget-0:sql": { label: "Generating SQL", status: "done", parentId: "widget-0", order: 2 },
      get_schema: { label: "Reading the schema", status: "done", parentId: null, order: 0 },
      "widget-0": { label: 'Building "Revenue"', status: "running", parentId: null, order: 1 },
    };
    // Act
    render(<ProgressChecklist steps={steps} />);
    // Assert — rendered in `order`, and the child is marked as nested
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      "✓Reading the schema",
      '◔Building "Revenue"',
      "✓Generating SQL",
    ]);
    expect(items[2].className).toContain("checklist__item--child");
  });

  test("shows the failed glyph for a failed step", () => {
    // Arrange
    const steps: ProgressSteps = {
      "widget-1": { label: "Building X", status: "failed", parentId: null, order: 0 },
    };
    // Act
    render(<ProgressChecklist steps={steps} />);
    // Assert
    expect(screen.getByText("✕")).toBeTruthy();
  });
});
