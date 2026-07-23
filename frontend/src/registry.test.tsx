import { JSONUIProvider, Renderer, type Spec } from "@json-render/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

// A canvas has no 2D context in jsdom, so a real Chart.js constructor throws in an effect and
// unmounts the tree. Stub it (as ChartJsView.test does) — these tests assert the rendered DOM
// and the off-screen data-table that carries the chart's keyboard cross-filter controls.
vi.mock("chart.js", () => {
  class FakeChart {
    static register = vi.fn();
    data: Record<string, unknown> = { labels: [], datasets: [] };
    options: Record<string, unknown> = {};
    update = vi.fn();
    destroy = vi.fn();
  }
  return { Chart: FakeChart, registerables: [] };
});

import { registry } from "./registry";

afterEach(cleanup);

// Render a dashboard spec the way the app does — one provider seeding the shared state model
// (widget rows keyed by id, plus an optional /crossFilter selection) that $state resolves against.
function renderDashboard(spec: Spec, state: Record<string, unknown>) {
  return render(
    <JSONUIProvider registry={registry} initialState={state}>
      <Renderer spec={spec} registry={registry} />
    </JSONUIProvider>,
  );
}

function chart(id: string, labelColumn: string, stateKey: string): Spec["elements"][string] {
  return {
    type: "ChartJs",
    props: { kind: "bar", title: id, labelColumn, valueColumns: ["count"], data: { $state: `/${stateKey}/rows` } },
    children: [],
  };
}

const CATEGORY_CHART: Spec = {
  root: "root",
  elements: {
    root: { type: "Stack", props: {}, children: ["c"] },
    c: chart("By category", "category", "cat"),
  },
};

describe("ChartJs cross-filter wiring", () => {
  test("as the selection's own dimension: keeps every mark and emphasises the active one", () => {
    renderDashboard(CATEGORY_CHART, {
      cat: { rows: [{ category: "Books", count: 3 }, { category: "Toys", count: 9 }] },
      crossFilter: { category: "Books" },
    });
    const chartTable = within(screen.getByRole("table", { name: /By category/i }));
    // Both bars remain (a source is not filtered down to one), and Books is marked active.
    expect(chartTable.getByRole("button", { name: "Toys" })).toBeTruthy();
    expect(chartTable.getByRole("button", { name: "Books" }).getAttribute("aria-pressed")).toBe("true");
  });

  test("as a target of a filter on another column: filters its rows to matches", () => {
    const spec: Spec = {
      root: "root",
      elements: { root: { type: "Stack", props: {}, children: ["c"] }, c: chart("Over time", "month", "ts") },
    };
    renderDashboard(spec, {
      ts: { rows: [{ month: "Jan", category: "Books", count: 3 }, { month: "Feb", category: "Toys", count: 9 }] },
      crossFilter: { category: "Books" },
    });
    const chartTable = within(screen.getByRole("table", { name: /Over time/i }));
    expect(chartTable.getByRole("button", { name: "Jan" })).toBeTruthy();
    expect(chartTable.queryByRole("button", { name: "Feb" })).toBeNull();
  });
});

describe("coordinated cross-filtering across widgets", () => {
  const dashboard: Spec = {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["c", "t"] },
      c: chart("By category", "category", "cat"),
      t: { type: "DataTable", props: { data: { $state: "/detail" } }, children: [] },
    },
  };

  test("selecting a category in the chart filters a sibling table sharing that column (E1)", () => {
    renderDashboard(dashboard, {
      cat: { rows: [{ category: "Books", count: 3 }, { category: "Toys", count: 9 }] },
      detail: {
        columns: ["category", "amount"],
        rows: [{ category: "Books", amount: 1 }, { category: "Toys", amount: 2 }, { category: "Books", amount: 5 }],
      },
    });
    const table = () => within(screen.getByRole("group", { name: /data table/i }));
    expect(table().getAllByRole("button", { name: "Books" }).length).toBe(2); // both Books rows shown
    expect(table().getByRole("button", { name: "Toys" })).toBeTruthy();

    // Click the chart's Books mark (its keyboard/AT control) → the table focuses to Books rows.
    fireEvent.click(within(screen.getByRole("table", { name: /By category/i })).getByRole("button", { name: "Books" }));
    expect(table().getAllByRole("button", { name: "Books" }).length).toBe(2);
    expect(table().queryByRole("button", { name: "Toys" })).toBeNull();
  });

  test("a sibling that does not carry the selected column is left untouched (E5)", () => {
    renderDashboard(
      {
        root: "root",
        elements: {
          root: { type: "Stack", props: {}, children: ["c", "t"] },
          c: chart("By category", "category", "cat"),
          t: { type: "DataTable", props: { data: { $state: "/detail" } }, children: [] },
        },
      },
      {
        cat: { rows: [{ category: "Books", count: 3 }, { category: "Toys", count: 9 }] },
        detail: { columns: ["month", "total"], rows: [{ month: "Jan", total: 1 }, { month: "Feb", total: 2 }] },
      },
    );
    fireEvent.click(within(screen.getByRole("table", { name: /By category/i })).getByRole("button", { name: "Books" }));
    const table = within(screen.getByRole("group", { name: /data table/i }));
    // The month table shares no column with the selection, so both months remain.
    expect(table.getByRole("button", { name: "Jan" })).toBeTruthy();
    expect(table.getByRole("button", { name: "Feb" })).toBeTruthy();
  });

  test("two filters compose (AND) across the shared columns", () => {
    const spec: Spec = {
      root: "root",
      elements: { root: { type: "Stack", props: {}, children: ["t"] }, t: { type: "DataTable", props: { data: { $state: "/detail" } }, children: [] } },
    };
    renderDashboard(spec, {
      detail: {
        columns: ["category", "channel", "amount"],
        rows: [
          { category: "Books", channel: "web", amount: 1 },
          { category: "Books", channel: "store", amount: 2 },
          { category: "Toys", channel: "web", amount: 3 },
        ],
      },
      crossFilter: { category: "Books", channel: "web" },
    });
    const table = within(screen.getByRole("group", { name: /data table/i }));
    // Only the Books+web row survives the AND of both selections.
    expect(table.getAllByRole("row").length).toBe(2); // header + one data row
    expect(table.queryByRole("button", { name: "store" })).toBeNull();
    expect(table.queryByRole("button", { name: "Toys" })).toBeNull();
  });

  test("a filter combination that matches no rows renders an empty-state note", () => {
    const spec: Spec = {
      root: "root",
      elements: { root: { type: "Stack", props: {}, children: ["t"] }, t: { type: "DataTable", props: { data: { $state: "/detail" } }, children: [] } },
    };
    renderDashboard(spec, {
      detail: { columns: ["category"], rows: [{ category: "Books" }, { category: "Toys" }] },
      crossFilter: { category: "Nonexistent" },
    });
    expect(screen.getByRole("status").textContent).toMatch(/no rows match/i);
  });
});
