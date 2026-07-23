// How the "@" menu narrows a list of names. Shared by the table and column menus so the
// two behave identically — a menu that ranked or capped differently depending on what it
// held would just be a second thing to learn.

/** A menu longer than this stops being scannable and starts hiding the transcript. */
export const MENU_LENGTH = 8;

/**
 * The names matching `query`, those starting with it first.
 *
 * Matching anywhere (not just the start) is what makes a prefixed warehouse table findable
 * by the part its users think of as the name; ranking prefixes first is what stops that
 * generosity from burying the obvious answer.
 *
 * Example:
 *     rankedMatches(["northwind_order_details", "orders"], "order");
 *     // ["orders", "northwind_order_details"]
 */
export function rankedMatches(names: string[], query: string): string[] {
  const needle = query.toLowerCase();
  const matches = names.filter((name) => name.toLowerCase().includes(needle));
  matches.sort((a, b) => rankFor(a, needle) - rankFor(b, needle));
  return matches;
}

/** 0 when the name starts with what was typed, 1 when it only contains it. */
function rankFor(name: string, needle: string): number {
  return name.toLowerCase().startsWith(needle) ? 0 : 1;
}

/**
 * The names to show in the "@" menu for `query`: capped while filtering, uncapped while
 * browsing.
 *
 * An empty query is the user browsing the whole list, not searching it — capping that hides
 * everything past the eighth name (a warehouse's later tables, a wide table's later columns)
 * behind a filter the user has no reason to know they need. The menu scrolls, so the full
 * list is reachable. Once anything is typed the cap returns, keeping a match list scannable.
 *
 * Example:
 *     rankedMenu(["a", "b", "c"], "");  // ["a", "b", "c"] — the whole list
 */
export function rankedMenu(names: string[], query: string): string[] {
  const ranked = rankedMatches(names, query);
  return query === "" ? ranked : ranked.slice(0, MENU_LENGTH);
}
