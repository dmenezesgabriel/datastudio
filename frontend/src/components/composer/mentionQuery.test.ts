import { expect, test } from "vitest";

import { matchingColumns, parseMentionQuery } from "./mentionQuery";

const TABLES = ["olist_orders", "olist_products"];

test("what is typed after @ names a table until a dot appears", () => {
  expect(parseMentionQuery("olist", TABLES)).toEqual({ kind: "table", query: "olist" });
});

test("a dot after a known table switches to naming its columns", () => {
  expect(parseMentionQuery("olist_orders.", TABLES)).toEqual({
    kind: "column",
    table: "olist_orders",
    query: "",
  });
});

test("what follows the dot narrows the columns", () => {
  expect(parseMentionQuery("olist_orders.order_", TABLES)).toEqual({
    kind: "column",
    table: "olist_orders",
    query: "order_",
  });
});

test("a dot after something that is not a table offers nothing", () => {
  // Better an empty menu than a confident menu for a table the dataset does not have.
  expect(parseMentionQuery("nonsense.", TABLES)).toBeNull();
});

test("only the first dot separates the table from the column", () => {
  // A column name may itself contain a dot; the table is whatever precedes the first one.
  expect(parseMentionQuery("olist_orders.a.b", TABLES)).toEqual({
    kind: "column",
    table: "olist_orders",
    query: "a.b",
  });
});

test("an empty query offers every table", () => {
  expect(parseMentionQuery("", TABLES)).toEqual({ kind: "table", query: "" });
});

test("matches columns by what has been typed, case-insensitively", () => {
  const columns = ["order_id", "customer_id", "Order_Status"];
  expect(matchingColumns(columns, "order")).toEqual(["order_id", "Order_Status"]);
});

test("offers every column before anything is typed after the dot", () => {
  expect(matchingColumns(["a", "b"], "")).toEqual(["a", "b"]);
});

test("keeps the column menu short enough to scan", () => {
  const many = Array.from({ length: 40 }, (_, i) => `col_${i}`);
  expect(matchingColumns(many, "col").length).toBe(8);
});

test("offers the whole table to browse before anything is typed after the dot", () => {
  // Same as the table menu: a bare "table." is browsing the columns, so the cap that keeps a
  // filtered list scannable would instead hide a wide table's later columns behind a filter.
  const many = Array.from({ length: 40 }, (_, i) => `col_${i}`);
  expect(matchingColumns(many, "").length).toBe(40);
});
