import { describe, expect, test } from "vitest";

import {
  activeCount,
  activeIndicesFor,
  applyFilters,
  isActive,
  matchesAllFilters,
  pruneFilters,
  rowsHaveField,
  sameValue,
  valuesFor,
  withField,
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

describe("isActive / valuesFor / activeCount", () => {
  test("isActive reflects whether a value is in the field's selected set", () => {
    expect(isActive({ category: ["Books", "Toys"] }, "category", "Books")).toBe(true);
    expect(isActive({ category: ["Books"] }, "category", "Toys")).toBe(false);
    expect(isActive({}, "category", "Books")).toBe(false);
  });

  test("valuesFor returns the selected set or a stable empty array", () => {
    expect(valuesFor({ category: ["Books", "Toys"] }, "category")).toEqual(["Books", "Toys"]);
    expect(valuesFor({ category: ["Books"] }, "region")).toEqual([]);
    // Same empty reference each call so an unfiltered field doesn't churn renders.
    expect(valuesFor({}, "region")).toBe(valuesFor({}, "category"));
  });

  test("activeCount counts the filtered fields (not values)", () => {
    expect(activeCount({})).toBe(0);
    expect(activeCount({ category: ["Books", "Toys"], region: ["West"] })).toBe(2);
  });
});

describe("withField (the one home for the set mutation)", () => {
  test("sets a field's whole value set on a new object", () => {
    const filters = { region: ["West"] };
    expect(withField(filters, "category", ["Books", "Toys"])).toEqual({
      region: ["West"],
      category: ["Books", "Toys"],
    });
    expect(withField(filters, "category", ["Books"])).not.toBe(filters); // never mutates
  });

  test("omits the key entirely when the value set is empty", () => {
    expect(withField({ category: ["Books"], region: ["West"] }, "category", [])).toEqual({
      region: ["West"],
    });
    expect("category" in withField({ category: ["Books"] }, "category", [])).toBe(false);
  });
});

describe("matchesAllFilters (OR within a field, AND across fields, absent fields ignored)", () => {
  test("a row matches when its value is IN the field's set, for every carried field", () => {
    // category IN (Books, Electronics) AND region IN (West)
    const filters = { category: ["Books", "Electronics"], region: ["West"] };
    expect(matchesAllFilters(ROWS[0], filters)).toBe(true); // Electronics/West
    expect(matchesAllFilters(ROWS[1], filters)).toBe(true); // Books/West
    expect(matchesAllFilters(ROWS[2], filters)).toBe(false); // Electronics/East — region excludes
  });

  test("a value outside the field's set excludes the row", () => {
    expect(matchesAllFilters(ROWS[1], { category: ["Electronics"] })).toBe(false);
  });

  test("a filter on a field the row lacks does not exclude it (safe no-op)", () => {
    expect(matchesAllFilters({ month: "Jan" }, { category: ["Books"] })).toBe(true);
  });

  test("excludeField skips one field (a chart emphasising its own dimension)", () => {
    // Filtering by region only, ignoring the category selection on the chart's own axis.
    expect(
      matchesAllFilters(ROWS[1], { category: ["Electronics"], region: ["West"] }, "category"),
    ).toBe(true);
  });
});

describe("applyFilters", () => {
  test("keeps rows matching ALL active selections (OR within, AND across)", () => {
    expect(applyFilters(ROWS, { category: ["Books", "Electronics"], region: ["West"] })).toEqual([
      { category: "Electronics", region: "West", total: 120 },
      { category: "Books", region: "West", total: 40 },
    ]);
  });

  test("is a no-op (same ref) when there are no filters", () => {
    expect(applyFilters(ROWS, {})).toBe(ROWS);
  });

  test("is a no-op when the rows carry none of the filtered fields", () => {
    const timeRows = [{ month: "Jan", total: 3 }];
    expect(applyFilters(timeRows, { category: ["Books"] })).toBe(timeRows);
  });

  test("excludeField removes one field from the predicate", () => {
    // A chart grouped by category, with a region filter active: keep all categories in West.
    expect(applyFilters(ROWS, { category: ["Books"], region: ["West"] }, "category")).toEqual([
      { category: "Electronics", region: "West", total: 120 },
      { category: "Books", region: "West", total: 40 },
    ]);
  });

  test("tolerates null/undefined cells", () => {
    const rows = [{ category: null }, { category: "Books" }, { category: undefined }];
    expect(applyFilters(rows, { category: ["Books"] })).toEqual([{ category: "Books" }]);
  });
});

describe("pruneFilters (reconcile a selection to the current dimensions)", () => {
  // The dimensions an edited dashboard still offers: category (Toys only) and region (West, East).
  const DIMENSIONS = [
    { field: "category", options: [{ value: "Toys" }] },
    { field: "region", options: [{ value: "West" }, { value: "East" }] },
  ];

  test("keeps values still selectable (same ref, no churn)", () => {
    const filters = { region: ["West", "East"] };
    expect(pruneFilters(filters, DIMENSIONS)).toBe(filters);
  });

  test("drops a field no longer offered (edit removed the column)", () => {
    expect(pruneFilters({ supplier: ["Acme"], region: ["West"] }, DIMENSIONS)).toEqual({
      region: ["West"],
    });
  });

  test("drops just the values a dimension no longer yields, keeping the rest", () => {
    // "Books" is gone but "Toys" survives on category; "East" survives on region.
    expect(pruneFilters({ category: ["Books", "Toys"], region: ["East"] }, DIMENSIONS)).toEqual({
      category: ["Toys"],
      region: ["East"],
    });
  });

  test("drops a field when none of its values survive", () => {
    expect(pruneFilters({ category: ["Books"], region: ["West"] }, DIMENSIONS)).toEqual({
      region: ["West"],
    });
  });

  test("empty dimensions (a text-only edit) drop every selection", () => {
    expect(pruneFilters({ category: ["Toys"], region: ["West"] }, [])).toEqual({});
  });

  test("an already-empty selection is returned as the same (empty) reference", () => {
    const none = {};
    expect(pruneFilters(none, DIMENSIONS)).toBe(none);
  });
});

describe("activeIndicesFor", () => {
  test("returns every row index whose field value is selected", () => {
    expect(activeIndicesFor(ROWS, "category", { category: ["Electronics"] })).toEqual(
      new Set([0, 2]),
    );
    expect(activeIndicesFor(ROWS, "category", { category: ["Books", "Electronics"] })).toEqual(
      new Set([0, 1, 2]),
    );
  });

  test("returns an empty set when the field is not selected or nothing matches", () => {
    expect(activeIndicesFor(ROWS, "category", { region: ["West"] })).toEqual(new Set());
    expect(activeIndicesFor(ROWS, "category", { category: ["Toys"] })).toEqual(new Set());
    expect(activeIndicesFor(ROWS, "category", {})).toEqual(new Set());
  });
});
