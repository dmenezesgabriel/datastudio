import { describe, expect, test } from "vitest";

import {
  activeCount,
  activeIndexFor,
  applyFilters,
  isActive,
  matchesAllFilters,
  pruneFilters,
  rowsHaveField,
  sameValue,
  valueFor,
} from "./crossFilter";

// A widget's rows share the shape the renderer resolves from /widget-N/rows.
const ROWS = [
  { category: "Electronics", region: "West", total: 120 },
  { category: "Books", region: "West", total: 40 },
  { category: "Electronics", region: "East", total: 5 },
];

describe("sameValue", () => {
  test("compares primitives by identity, without coercion", () => {
    expect(sameValue("Books", "Books")).toBe(true);
    expect(sameValue(2017, 2017)).toBe(true);
    expect(sameValue(40, "40")).toBe(false);
  });
});

describe("rowsHaveField", () => {
  test("is true only when a row carries the column", () => {
    expect(rowsHaveField(ROWS, "category")).toBe(true);
    expect(rowsHaveField(ROWS, "supplier")).toBe(false);
    expect(rowsHaveField([], "category")).toBe(false);
  });
});

describe("isActive / valueFor / activeCount", () => {
  test("isActive reflects a field's current selection", () => {
    expect(isActive({ category: "Books" }, "category", "Books")).toBe(true);
    expect(isActive({ category: "Books" }, "category", "Toys")).toBe(false);
    expect(isActive({}, "category", "Books")).toBe(false);
  });

  test("valueFor returns the selected value or undefined", () => {
    expect(valueFor({ category: "Books" }, "category")).toBe("Books");
    expect(valueFor({ category: "Books" }, "region")).toBeUndefined();
  });

  test("activeCount counts the active fields", () => {
    expect(activeCount({})).toBe(0);
    expect(activeCount({ category: "Books", region: "West" })).toBe(2);
  });
});

describe("matchesAllFilters (AND-composed, absent fields ignored)", () => {
  test("a row must match every active field it carries", () => {
    expect(matchesAllFilters(ROWS[0], { category: "Electronics", region: "West" })).toBe(true);
    expect(matchesAllFilters(ROWS[2], { category: "Electronics", region: "West" })).toBe(false);
  });

  test("a filter on a field the row lacks does not exclude it (safe no-op)", () => {
    expect(matchesAllFilters({ month: "Jan" }, { category: "Books" })).toBe(true);
  });

  test("excludeField skips one field (a chart emphasising its own dimension)", () => {
    // Filtering by region only, ignoring the category selection on the chart's own axis.
    expect(matchesAllFilters(ROWS[1], { category: "Electronics", region: "West" }, "category")).toBe(true);
  });
});

describe("applyFilters", () => {
  test("keeps rows matching ALL active selections", () => {
    expect(applyFilters(ROWS, { category: "Electronics", region: "West" })).toEqual([
      { category: "Electronics", region: "West", total: 120 },
    ]);
  });

  test("is a no-op (same ref) when there are no filters", () => {
    expect(applyFilters(ROWS, {})).toBe(ROWS);
  });

  test("is a no-op when the rows carry none of the filtered fields", () => {
    const timeRows = [{ month: "Jan", total: 3 }];
    expect(applyFilters(timeRows, { category: "Books" })).toBe(timeRows);
  });

  test("excludeField removes one field from the predicate", () => {
    // A chart grouped by category, with a region filter active: keep all categories in West.
    expect(applyFilters(ROWS, { category: "Books", region: "West" }, "category")).toEqual([
      { category: "Electronics", region: "West", total: 120 },
      { category: "Books", region: "West", total: 40 },
    ]);
  });

  test("tolerates null/undefined cells", () => {
    const rows = [{ category: null }, { category: "Books" }, { category: undefined }];
    expect(applyFilters(rows, { category: "Books" })).toEqual([{ category: "Books" }]);
  });
});

describe("pruneFilters (reconcile a selection to the current dimensions)", () => {
  // The dimensions an edited dashboard still offers: category (Toys only) and region (West).
  const DIMENSIONS = [
    { field: "category", options: [{ value: "Toys" }] },
    { field: "region", options: [{ value: "West" }, { value: "East" }] },
  ];

  test("keeps selections whose field and value are still selectable (same ref, no churn)", () => {
    const filters = { region: "West" };
    expect(pruneFilters(filters, DIMENSIONS)).toBe(filters);
  });

  test("drops a selection whose field is no longer a dimension (edit removed the column)", () => {
    expect(pruneFilters({ supplier: "Acme", region: "West" }, DIMENSIONS)).toEqual({ region: "West" });
  });

  test("drops a selection whose value the dimension no longer yields (edit changed the data)", () => {
    // "Books" was selected, but the edited category dimension now offers only "Toys".
    expect(pruneFilters({ category: "Books" }, DIMENSIONS)).toEqual({});
  });

  test("empty dimensions (a text-only edit) drop every selection", () => {
    expect(pruneFilters({ category: "Toys", region: "West" }, [])).toEqual({});
  });

  test("an already-empty selection is returned as the same (empty) reference", () => {
    const none = {};
    expect(pruneFilters(none, DIMENSIONS)).toBe(none);
  });
});

describe("activeIndexFor", () => {
  test("returns the first row index matching the selection on that field", () => {
    expect(activeIndexFor(ROWS, "category", { category: "Books" })).toBe(1);
  });

  test("returns null when the field is not selected or nothing matches", () => {
    expect(activeIndexFor(ROWS, "category", { region: "West" })).toBeNull();
    expect(activeIndexFor(ROWS, "category", { category: "Toys" })).toBeNull();
    expect(activeIndexFor(ROWS, "category", {})).toBeNull();
  });
});
