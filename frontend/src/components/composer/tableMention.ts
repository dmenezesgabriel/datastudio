import { type Node as ProseMirrorNode } from "prosemirror-model";
import { type Command, type EditorState, TextSelection } from "prosemirror-state";

import { composerSchema, columnMentionNode, tableMentionNode } from "./composerSchema";
import { rankedMenu } from "./matching";

// Typing "@" opens the table menu. Recognising that is pure work over the document, so it
// lives here as a function rather than inside a plugin — it can be reasoned about, and
// tested, without a browser or an editor view.

/** The "@query" the caret currently sits in, and the range it occupies. */
export type MentionTrigger = {
  /** What has been typed after the "@" — "" the moment it is typed. */
  query: string;
  /** Start of the "@" (or of the chip being drilled), so the whole trigger can be replaced. */
  from: number;
  /** The caret. */
  to: number;
  /**
   * Set when the trigger is a ".column" drilled from a table chip already in the document
   * rather than a typed "@". The query then names a column of this table, and the range
   * (from..to) spans the chip so picking a column replaces it with a qualified column chip.
   */
  chipTable?: string;
};

// An "@" only opens the menu at the start of a word, so an email address does not. The name
// itself cannot contain whitespace: a space means the user has finished referring to it.
const MENTION_TRIGGER = /(?:^|\s)@(\S*)$/;

// A chip is an atom; read as one placeholder character so its name is not mistaken for typed
// text and the offsets still line up with the document (U+FFFC, OBJECT REPLACEMENT CHARACTER).
const CHIP_PLACEHOLDER = "￼";

// A committed table chip, an optional single space, then the ".column" being typed at the
// caret: the user drilling into a chip they already placed. The optional space is the one
// insertTableMention leaves after the chip — the drill has to work with it or without it.
const CHIP_COLUMN_TRIGGER = new RegExp(`${CHIP_PLACEHOLDER} ?\\.(\\S*)$`);

// How far back to look for the trigger. A table name is far shorter than this, and scanning
// a whole paragraph on every keystroke is work that grows with the question's length.
const TRIGGER_LOOKBEHIND = 50;

/**
 * The table reference being typed at the caret, or null when the menu should stay shut.
 *
 * Recognises both a typed "@query" and a ".column" drilled from a table chip already placed
 * (see ``chipTable`` on the result).
 *
 * Example:
 *     findMentionTrigger(state); // { query: "oli", from: 9, to: 13 }
 */
export function findMentionTrigger(state: EditorState): MentionTrigger | null {
  const { $from, empty } = state.selection;
  if (!empty || !$from.parent.isTextblock) return null;

  const start = Math.max(0, $from.parentOffset - TRIGGER_LOOKBEHIND);
  const before = $from.parent.textBetween(start, $from.parentOffset, undefined, CHIP_PLACEHOLDER);

  const typed = MENTION_TRIGGER.exec(before);
  if (typed !== null) {
    const query = typed[1];
    return { query, from: $from.pos - query.length - 1, to: $from.pos };
  }
  return chipColumnTrigger(state, $from.pos, before);
}

/** A ".column" being typed straight after a table chip, or null when it is anything else. */
function chipColumnTrigger(
  state: EditorState,
  caret: number,
  before: string,
): MentionTrigger | null {
  const match = CHIP_COLUMN_TRIGGER.exec(before);
  if (match === null) return null;
  // Each character in `before` is one document position (text char or atom placeholder), so
  // the match's length is exactly the span it covers — its start is where the chip sits.
  const from = caret - match[0].length;
  const chip = state.doc.nodeAt(from);
  if (chip === null || chip.type.name !== "tableMention") return null;
  return { query: match[1], from, to: caret, chipTable: String(chip.attrs.name) };
}

/**
 * The tables worth offering for `query`, best-first and capped to a scannable menu.
 *
 * Example:
 *     matchingTables(["events", "event_log", "customers"], "ev"); // ["events", "event_log"]
 */
export function matchingTables(tables: string[], query: string | undefined): string[] {
  if (query === undefined) return [];
  return rankedMenu(tables, query);
}

/**
 * Replace a typed "@query" with the chip for `tableName`, followed by a space.
 *
 * Example:
 *     insertTableMention(trigger, "events")(view.state, view.dispatch);
 */
export function insertTableMention(trigger: MentionTrigger, tableName: string): Command {
  return replaceTriggerWith(trigger, tableMentionNode(tableName));
}

/**
 * Replace a typed "@table.query" with the chip for `column`, followed by a space.
 *
 * Example:
 *     insertColumnMention(trigger, "events", "amount")(view.state, view.dispatch);
 */
export function insertColumnMention(
  trigger: MentionTrigger,
  table: string,
  column: string,
): Command {
  return replaceTriggerWith(trigger, columnMentionNode(table, column));
}

/** Swap the typed "@query" for `chip`, leaving the caret past the space that follows it. */
function replaceTriggerWith(trigger: MentionTrigger, chip: ProseMirrorNode): Command {
  return (state, dispatch) => {
    if (!dispatch) return true;
    // The trailing space lets the user carry on typing rather than landing against the chip.
    const tr = state.tr.replaceWith(trigger.from, trigger.to, [chip, composerSchema.text(" ")]);
    tr.setSelection(TextSelection.create(tr.doc, trigger.from + chip.nodeSize + 1));
    dispatch(tr.scrollIntoView());
    return true;
  };
}

/**
 * Replace a typed "@query" with `query`, leaving the mention open for more typing.
 *
 * Used to carry a highlighted table into its columns: the reference is still being
 * written, so it stays text rather than becoming a chip.
 *
 * Example:
 *     typeMentionQuery(trigger, "events.")(view.state, view.dispatch);
 */
export function typeMentionQuery(trigger: MentionTrigger, query: string): Command {
  return (state, dispatch) => {
    if (!dispatch) return true;
    const tr = state.tr.replaceWith(trigger.from, trigger.to, composerSchema.text(`@${query}`));
    dispatch(tr.scrollIntoView());
    return true;
  };
}
