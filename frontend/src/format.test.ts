import { expect, test } from "vitest";

import { formatCell, formatLabel, formatValue, isNumericColumn } from "./format";

test("formatValue adds thousands separators to integers", () => {
  expect(formatValue(99441)).toBe("99,441");
});

test("formatValue rounds a raw float to two decimals with separators", () => {
  // The KPI card used to render "16008872.119998764"; it should read like money.
  expect(formatValue(16008872.119998764)).toBe("16,008,872.12");
});

test("formatValue rounds a numeric string", () => {
  expect(formatValue("160.99026669347109")).toBe("160.99");
});

test("formatValue leaves non-numeric text unchanged", () => {
  expect(formatValue("credit_card")).toBe("credit_card");
});

test("formatValue renders null/undefined as empty string", () => {
  expect(formatValue(null)).toBe("");
  expect(formatValue(undefined)).toBe("");
});

test("formatValue renders a non-finite number as empty, not 'NaN'/'∞'", () => {
  // A divide-by-zero KPI ratio or an aggregate over zero rows arrives as NaN/Infinity.
  expect(formatValue(NaN)).toBe("");
  expect(formatValue(Infinity)).toBe("");
  expect(formatValue(-Infinity)).toBe("");
});

test("formatLabel collapses a midnight ISO timestamp to its date", () => {
  // A monthly axis used to show "0:00:00"; it should show the date.
  expect(formatLabel("2017-01-01T00:00:00")).toBe("2017-01-01");
});

test("formatLabel leaves category labels unchanged", () => {
  expect(formatLabel("on_time")).toBe("on_time");
  expect(formatLabel(3)).toBe("3");
});

test("formatLabel renders a null/undefined category as an empty tick, not 'null'", () => {
  expect(formatLabel(null)).toBe("");
  expect(formatLabel(undefined)).toBe("");
});

test("formatCell cleans a fractional measure's float artifact", () => {
  expect(formatCell(16008872.119998764)).toBe("16,008,872.12");
});

test("formatCell leaves integers plain so years and ids are not corrupted", () => {
  expect(formatCell(2017)).toBe("2017");
  expect(formatCell(99441)).toBe("99441");
});

test("formatCell passes strings through and renders null as empty", () => {
  expect(formatCell("credit_card")).toBe("credit_card");
  expect(formatCell(null)).toBe("");
});

test("formatCell renders a non-finite number as empty, not 'NaN'/'∞'", () => {
  expect(formatCell(NaN)).toBe("");
  expect(formatCell(Infinity)).toBe("");
});

test("isNumericColumn is true when every present cell reads as a number", () => {
  const rows = [{ amount: 12, city: "Rio" }, { amount: "3.5", city: "Sampa" }];
  expect(isNumericColumn(rows, "amount")).toBe(true);
  expect(isNumericColumn(rows, "city")).toBe(false);
});

test("isNumericColumn ignores null/empty cells but needs at least one value", () => {
  expect(isNumericColumn([{ n: null }, { n: 5 }], "n")).toBe(true);
  expect(isNumericColumn([{ n: null }, { n: "" }], "n")).toBe(false);
  expect(isNumericColumn([], "n")).toBe(false);
});
