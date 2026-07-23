import { afterEach, describe, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { DataTable, Grid, KpiRow, KpiStat } from "./Panels";

afterEach(cleanup);

describe("DataTable", () => {
  test("wraps the table in a keyboard-focusable scroll region", () => {
    // A horizontally-scrolling table region must be reachable by keyboard to scroll it
    // (WCAG 2.1.1). axe flags a scrollable region with no focusable access.
    render(<DataTable columns={["city", "orders"]} rows={[["Sampa", "42"]]} numericColumns={[false, true]} />);
    const region = screen.getByRole("group", { name: /data table/i });
    expect(region.getAttribute("tabindex")).toBe("0");
  });

  test("renders every supplied row inside the scroll region", () => {
    // A tall result is height-capped and scrolls inside .table-scroll — in the dashboard grid
    // at the standardized --widget-body-height, so it ends level with the chart beside it
    // (verified live in Playwright — jsdom has no layout). Here we only guard that the wrapper
    // never drops rows: the whole point of the scroll box is to hold *all* of them.
    const rows = Array.from({ length: 50 }, (_, index) => [`city-${index}`, String(index)]);
    const { container } = render(
      <DataTable columns={["city", "orders"]} rows={rows} numericColumns={[false, true]} />,
    );
    const region = screen.getByRole("group", { name: /data table/i });
    expect(region.classList.contains("table-scroll")).toBe(true);
    expect(container.querySelectorAll("tbody tr").length).toBe(50);
  });

  test("renders plain (non-interactive) cells when no selection handler is given", () => {
    const { container } = render(
      <DataTable columns={["city", "orders"]} rows={[["Sampa", "42"]]} numericColumns={[false, true]} />,
    );
    expect(container.querySelector("button")).toBeNull();
  });

  test("makes a filterable (non-numeric) cell a button that emits its column and raw value", () => {
    // Selection drives the cross-filter, so the raw cell value is emitted (not the formatted
    // display string) — the filter compares against unformatted row values.
    const onSelectCell = vi.fn();
    render(
      <DataTable
        columns={["city", "orders"]}
        rows={[["Sampa", "42"]]}
        rawRows={[["Sampa", 42]]}
        numericColumns={[false, true]}
        onSelectCell={onSelectCell}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sampa" }));
    expect(onSelectCell).toHaveBeenCalledWith("city", "Sampa");
  });

  test("leaves numeric cells as plain text even when selection is enabled", () => {
    // Filtering by a measure is meaningless; only dimension (text) columns are selectable.
    render(
      <DataTable
        columns={["city", "orders"]}
        rows={[["Sampa", "42"]]}
        rawRows={[["Sampa", 42]]}
        numericColumns={[false, true]}
        onSelectCell={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: "42" })).toBeNull();
  });

  test("marks cells matching any active filter with aria-pressed", () => {
    render(
      <DataTable
        columns={["city", "channel"]}
        rows={[
          ["Sampa", "web"],
          ["Rio", "store"],
        ]}
        rawRows={[
          ["Sampa", "web"],
          ["Rio", "store"],
        ]}
        numericColumns={[false, false]}
        onSelectCell={vi.fn()}
        activeValues={{ city: ["Rio"], channel: ["web"] }}
      />,
    );
    // Two independent filters (AND) — each highlights its own matching cell.
    expect(screen.getByRole("button", { name: "Rio" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "web" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Sampa" }).getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: "store" }).getAttribute("aria-pressed")).toBe("false");
  });

  test("marks every cell whose value is in a column's selected set (multi-select)", () => {
    render(
      <DataTable
        columns={["city"]}
        rows={[["Sampa"], ["Rio"], ["Curitiba"]]}
        rawRows={[["Sampa"], ["Rio"], ["Curitiba"]]}
        numericColumns={[false]}
        onSelectCell={vi.fn()}
        activeValues={{ city: ["Sampa", "Curitiba"] }}
      />,
    );
    expect(screen.getByRole("button", { name: "Sampa" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Curitiba" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Rio" }).getAttribute("aria-pressed")).toBe("false");
  });
});

describe("KpiStat", () => {
  test("renders the value and label", () => {
    render(<KpiStat label="Total revenue" value="16,008,872.12" />);
    expect(screen.getByText("16,008,872.12")).toBeTruthy();
    expect(screen.getByText("Total revenue")).toBeTruthy();
  });

  test("omits the delta badge when no delta is given", () => {
    const { container } = render(<KpiStat label="X" value="1" />);
    expect(container.querySelector(".kpi-stat__delta")).toBeNull();
  });

  test("shows an up arrow and status class for a positive delta", () => {
    const { container } = render(
      <KpiStat label="X" value="1" delta={{ direction: "up", text: "+12 vs last month" }} />,
    );
    const badge = container.querySelector(".kpi-stat__delta--up");
    expect(badge?.textContent).toContain("▲");
    expect(badge?.textContent).toContain("+12 vs last month");
    // direction is also announced to screen readers, not conveyed by color alone
    expect(badge?.querySelector(".sr-only")?.textContent).toContain("up");
  });

  test("shows a down arrow and status class for a negative delta", () => {
    const { container } = render(
      <KpiStat label="X" value="1" delta={{ direction: "down", text: "-3" }} />,
    );
    const badge = container.querySelector(".kpi-stat__delta--down");
    expect(badge?.textContent).toContain("▼");
  });
});

describe("dashboard layout containers", () => {
  test("KpiRow wraps children in the kpi-row band", () => {
    const { container } = render(
      <KpiRow>
        <div>a</div>
      </KpiRow>,
    );
    expect(container.querySelector(".kpi-row")?.textContent).toBe("a");
  });

  test("Grid wraps children in the dash-grid region", () => {
    const { container } = render(
      <Grid>
        <div>b</div>
      </Grid>,
    );
    expect(container.querySelector(".dash-grid")?.textContent).toBe("b");
  });
});
