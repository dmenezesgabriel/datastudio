import { type Node as ProseMirrorNode } from "prosemirror-model";
import { type Command, type EditorState, TextSelection } from "prosemirror-state";

import { composerSchema, columnMentionNode, tableMentionNode } from "./composerSchema";
import { MENU_LENGTH, rankedMatches } from "./matching";

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

/**
 * The tables worth offering for `query`, best-first and capped to a scannable menu.
 *
 * Example:
 *     matchingTables(["events", "event_log", "customers"], "ev"); // ["events", "event_log"]
 */
export function matchingTables(tables: string[], query: string | undefined): string[] {
  if (query === undefined) return [];
  return rankedMatches(tables, query).slice(0, MENU_LENGTH);
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
