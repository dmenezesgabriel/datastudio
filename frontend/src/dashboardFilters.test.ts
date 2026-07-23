import type { Spec } from "@json-render/react";
import { describe, expect, test } from "vitest";

import { filterDimensions, humanizeField } from "./dashboardFilters";
import type { SpecWithState } from "./types";

// Mirrors the real persisted shape: a chart grouped by categoryName (its rows also carry a
// junk `bar` sparkline-text column) + a products table sharing categoryName.
function dashboard(): SpecWithState {
  return {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["c", "t", "k"] },
      c: {
        type: "ChartJs",
        props: { kind: "bar", title: "x", labelColumn: "categoryName", valueColumns: ["total"], data: { $state: "/w0/rows" } },
        children: [],
      },
      t: { type: "DataTable", props: { data: { $state: "/w1" } }, children: [] },
      k: { type: "KpiStat", props: { label: "n", valueColumn: "total", data: { $state: "/w2/rows" } }, children: [] },
    },
    state: {
      w0: {
        columns: ["categoryName", "total", "bar"],
        rows: [
          { categoryName: "Beverages", total: 5, bar: "####" },
          { categoryName: "Dairy", total: 3, bar: "##" },
        ],
      },
      w1: {
        columns: ["productName", "categoryName", "unitPrice"],
        rows: [
          { productName: "Chai", categoryName: "Beverages", unitPrice: 18 },
          { productName: "Queso", categoryName: "Dairy", unitPrice: 20 },
          { productName: "Chang", categoryName: "Beverages", unitPrice: 19 },
        ],
      },
      w2: { columns: ["total"], rows: [{ total: 100 }] },
    },
  };
}

describe("humanizeField", () => {
  test("turns camelCase and snake_case field names into readable labels", () => {
    expect(humanizeField("categoryName")).toBe("Category Name");
    expect(humanizeField("total_order_value")).toBe("Total Order Value");
    expect(humanizeField("category")).toBe("Category");
  });
});

describe("filterDimensions", () => {
  test("derives dimensions from chart labelColumns + table dimension columns, shared-first", () => {
    const dims = filterDimensions(dashboard() as Spec);
    expect(dims.map((d) => d.field)).toEqual(["categoryName", "productName"]);
  });

  test("marks a dimension shared when ≥2 widgets carry it, and labels it readably", () => {
    const [category] = filterDimensions(dashboard() as Spec);
    expect(category.shared).toBe(true); // chart + table
    expect(category.label).toBe("Category Name");
    expect(category.options.map((o) => o.value)).toEqual(["Beverages", "Dairy"]);
  });

  test("excludes numeric measures and the chart's non-label columns (e.g. the bar sparkline)", () => {
    const fields = filterDimensions(dashboard() as Spec).map((d) => d.field);
    expect(fields).not.toContain("unitPrice"); // numeric measure
    expect(fields).not.toContain("total"); // numeric measure
    expect(fields).not.toContain("bar"); // chart non-label column
  });

  test("gathers distinct, sorted options for a single-widget dimension", () => {
    const product = filterDimensions(dashboard() as Spec).find((d) => d.field === "productName");
    expect(product?.shared).toBe(false);
    expect(product?.options.map((o) => o.value)).toEqual(["Chai", "Chang", "Queso"]);
  });

  test("drops a dimension with fewer than two distinct values (nothing to filter)", () => {
    const spec = dashboard();
    // Every product in one category → categoryName in the table degenerates, but the chart
    // still has 2 categories, so it stays. Add a constant column to prove single-value drop.
    for (const row of (spec.state!.w1 as { rows: Record<string, unknown>[] }).rows) row.region = "West";
    (spec.state!.w1 as { columns: string[] }).columns.push("region");
    const fields = filterDimensions(spec as Spec).map((d) => d.field);
    expect(fields).not.toContain("region");
  });

  test("returns nothing for a dashboard with no chart or table dimensions", () => {
    const textOnly: SpecWithState = {
      root: "root",
      elements: { root: { type: "Stack", props: {}, children: ["m"] }, m: { type: "Markdown", props: { text: "hi" }, children: [] } },
      state: {},
    };
    expect(filterDimensions(textOnly as Spec)).toEqual([]);
  });
});
