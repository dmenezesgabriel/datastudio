import { type Command, type EditorState, TextSelection } from "prosemirror-state";

import { composerSchema, tableMentionNode } from "./composerSchema";

// Typing "@" opens the table menu. Recognising that is pure work over the document, so it
// lives here as a function rather than inside a plugin — it can be reasoned about, and
// tested, without a browser or an editor view.

/** The "@query" the caret currently sits in, and the range it occupies. */
export type MentionTrigger = {
  /** What has been typed after the "@" — "" the moment it is typed. */
  query: string;
  /** Start of the "@", so the whole trigger can be replaced by the chip. */
  from: number;
  /** The caret. */
  to: number;
};

// An "@" only opens the menu at the start of a word, so an email address does not. The name
// itself cannot contain whitespace: a space means the user has finished referring to it.
const MENTION_TRIGGER = /(?:^|\s)@(\S*)$/;

// How far back to look for the trigger. A table name is far shorter than this, and scanning
// a whole paragraph on every keystroke is work that grows with the question's length.
const TRIGGER_LOOKBEHIND = 50;

/**
 * The table reference being typed at the caret, or null when the menu should stay shut.
 *
 * Example:
 *     findMentionTrigger(state); // { query: "oli", from: 9, to: 13 }
 */
export function findMentionTrigger(state: EditorState): MentionTrigger | null {
  const { $from, empty } = state.selection;
  if (!empty || !$from.parent.isTextblock) return null;

  const start = Math.max(0, $from.parentOffset - TRIGGER_LOOKBEHIND);
  // A chip is an atom: read it as one placeholder character so its table name cannot be
  // mistaken for typed text, and so the offsets below still line up with the document.
  const before = $from.parent.textBetween(start, $from.parentOffset, undefined, "￼");
  const match = MENTION_TRIGGER.exec(before);
  if (match === null) return null;

  const query = match[1];
  return { query, from: $from.pos - query.length - 1, to: $from.pos };
}

// A menu longer than this stops being scannable and starts hiding the transcript behind it.
const MENU_LENGTH = 8;

/**
 * The tables worth offering for `query`, best-first and capped to a scannable menu.
 *
 * Example:
 *     matchingTables(["events", "event_log", "customers"], "ev"); // ["events", "event_log"]
 */
export function matchingTables(tables: string[], query: string | undefined): string[] {
  if (query === undefined) return [];
  const needle = query.toLowerCase();
  const matches = tables.filter((table) => table.toLowerCase().includes(needle));
  // A name that starts with what was typed is the likelier target than one that merely
  // contains it — "order" should reach "orders" before "northwind_order_details".
  matches.sort((a, b) => rankFor(a, needle) - rankFor(b, needle));
  return matches.slice(0, MENU_LENGTH);
}

/** 0 when the name starts with what was typed, 1 when it only contains it. */
function rankFor(table: string, needle: string): number {
  return table.toLowerCase().startsWith(needle) ? 0 : 1;
}

/**
 * Replace a typed "@query" with the chip for `tableName`, followed by a space.
 *
 * Example:
 *     insertTableMention(trigger, "events")(view.state, view.dispatch);
 */
export function insertTableMention(trigger: MentionTrigger, tableName: string): Command {
  return (state, dispatch) => {
    if (!dispatch) return true;
    const chip = tableMentionNode(tableName);
    // The trailing space lets the user carry on typing rather than landing against the chip.
    const tr = state.tr.replaceWith(trigger.from, trigger.to, [chip, composerSchema.text(" ")]);
    tr.setSelection(TextSelection.create(tr.doc, trigger.from + chip.nodeSize + 1));
    dispatch(tr.scrollIntoView());
    return true;
  };
}
