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
