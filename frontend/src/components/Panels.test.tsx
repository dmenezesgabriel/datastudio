import { afterEach, describe, expect, test } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

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
    // A tall result is height-capped and scrolls inside .table-scroll (verified live in
    // Playwright — jsdom has no layout). Here we only guard that the wrapper never drops
    // rows: the whole point of the scroll box is to hold *all* of them.
    const rows = Array.from({ length: 50 }, (_, index) => [`city-${index}`, String(index)]);
    const { container } = render(
      <DataTable columns={["city", "orders"]} rows={rows} numericColumns={[false, true]} />,
    );
    const region = screen.getByRole("group", { name: /data table/i });
    expect(region.classList.contains("table-scroll")).toBe(true);
    expect(container.querySelectorAll("tbody tr").length).toBe(50);
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
