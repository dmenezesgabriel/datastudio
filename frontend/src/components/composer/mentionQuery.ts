// What the "@" the user is part-way through typing currently refers to. A mention starts
// out naming a table and becomes a column reference the moment a dot follows a table the
// dataset actually has — so one trigger drives both menus, and reaching a column needs no
// second gesture to learn.

import { MENU_LENGTH, rankedMatches } from "./matching";

/** Which menu an in-progress "@" should be showing, and what to filter it by. */
export type MentionQuery =
  | { kind: "table"; query: string }
  | { kind: "column"; table: string; query: string };

/**
 * Read an in-progress "@query" as the reference it is turning into.
 *
 * Returns null when it names a table the dataset does not have, so no menu is offered for
 * something that cannot be referred to.
 *
 * Example:
 *     parseMentionQuery("events.amo", ["events"]);
 *     // { kind: "column", table: "events", query: "amo" }
 */
export function parseMentionQuery(query: string, tables: string[]): MentionQuery | null {
  const dot = query.indexOf(".");
  if (dot === -1) return { kind: "table", query };

  // Only the first dot separates the two: a column name may contain one, a table name
  // (as the engine lists it) does not.
  const table = query.slice(0, dot);
  if (!tables.includes(table)) return null;
  return { kind: "column", table, query: query.slice(dot + 1) };
}

/**
 * The columns worth offering for `query`, best-first and capped to a scannable menu.
 *
 * Example:
 *     matchingColumns(["order_id", "customer_id"], "order"); // ["order_id"]
 */
export function matchingColumns(columns: string[], query: string): string[] {
  return rankedMatches(columns, query).slice(0, MENU_LENGTH);
}
