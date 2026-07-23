import { expect, test } from "vitest";
import { EditorState, TextSelection } from "prosemirror-state";

import { composerSchema, docFromText, tableMentionNode } from "./composerSchema";
import {
  findMentionTrigger,
  insertColumnMention,
  insertTableMention,
  matchingTables,
} from "./tableMention";
import { draftToText } from "./composerDraft";

// A state holding `text` with the caret parked at its end — what the composer looks like
// mid-typing, which is the only moment the trigger matters.
function stateTyping(text: string): EditorState {
  const state = EditorState.create({ schema: composerSchema, doc: docFromText(text) });
  const end = state.doc.content.size - 1; // inside the paragraph, after its last character
  return state.apply(state.tr.setSelection(TextSelection.create(state.doc, end)));
}

// A state holding `prefix`, then a committed table chip, then `afterChip` — the caret parked
// at the end. This is what the document looks like when the user has already placed a table
// chip and is now typing ".column" to drill into it.
function stateAfterChip(prefix: string, table: string, afterChip: string): EditorState {
  const doc = composerSchema.node("doc", null, [
    composerSchema.node("paragraph", null, [
      composerSchema.text(prefix),
      tableMentionNode(table),
      composerSchema.text(afterChip),
    ]),
  ]);
  const state = EditorState.create({ schema: composerSchema, doc });
  const end = state.doc.content.size - 1;
  return state.apply(state.tr.setSelection(TextSelection.create(state.doc, end)));
}

test("offers the menu as soon as @ is typed", () => {
  expect(findMentionTrigger(stateTyping("rows in @"))?.query).toBe("");
});

test("narrows the menu with what is typed after the @", () => {
  expect(findMentionTrigger(stateTyping("rows in @olist"))?.query).toBe("olist");
});

test("triggers on an @ that opens the question", () => {
  expect(findMentionTrigger(stateTyping("@events"))?.query).toBe("events");
});

test("leaves an email address alone", () => {
  // An @ mid-word is an address, not a reference — popping a table menu over someone's
  // email would be wrong every time.
  expect(findMentionTrigger(stateTyping("mail me at ana@example.com"))).toBeNull();
});

test("closes the menu once the reference is finished with a space", () => {
  // The name cannot contain a space, so a space means the user has moved on.
  expect(findMentionTrigger(stateTyping("rows in @olist orders"))).toBeNull();
});

test("no menu when there is no @ at all", () => {
  expect(findMentionTrigger(stateTyping("revenue by month"))).toBeNull();
});

test("reports the range the @ occupies so it can be replaced", () => {
  const state = stateTyping("rows in @oli");
  const trigger = findMentionTrigger(state);

  // The range covers "@oli" — from the @ through the caret.
  expect(state.doc.textBetween(trigger!.from, trigger!.to)).toBe("@oli");
});

test("swaps the typed @query for the chip and a trailing space", () => {
  // The space is what lets the user keep typing straight after picking, instead of landing
  // glued to the chip.
  const state = stateTyping("rows in @oli");
  const trigger = findMentionTrigger(state)!;
  let next = state;

  insertTableMention(trigger, "olist_orders")(state, (tr) => {
    next = state.apply(tr);
  });

  expect(draftToText(next.doc)).toBe("rows in olist_orders ");
  expect(next.doc.firstChild?.child(1).type.name).toBe("tableMention");
});

test("puts the caret after the chip it just inserted", () => {
  const state = stateTyping("rows in @oli");
  const trigger = findMentionTrigger(state)!;
  let next = state;

  insertTableMention(trigger, "olist_orders")(state, (tr) => {
    next = state.apply(tr);
  });

  expect(next.selection.from).toBe(next.doc.content.size - 1);
});

test("an existing chip does not itself look like a trigger", () => {
  // The chip's own text is the table name; re-reading it as an @query would reopen the menu
  // every time the caret passed it.
  const doc = composerSchema.node("doc", null, [
    composerSchema.node("paragraph", null, [
      composerSchema.text("rows in "),
      tableMentionNode("olist_orders"),
    ]),
  ]);
  const state = EditorState.create({ schema: composerSchema, doc });
  const atEnd = state.apply(
    state.tr.setSelection(TextSelection.create(state.doc, state.doc.content.size - 1)),
  );

  expect(findMentionTrigger(atEnd)).toBeNull();
});

test("a dot typed after a committed table chip drills into that chip's columns", () => {
  // The whole "select the table, then get its columns" gesture: once a chip is placed, the
  // only pre-existing way to reach columns was gone. A dot after the chip reopens them.
  const trigger = findMentionTrigger(stateAfterChip("average ", "olist_orders", " ."));

  expect(trigger?.chipTable).toBe("olist_orders");
  expect(trigger?.query).toBe("");
});

test("narrows the chip's columns as the name after the dot is typed", () => {
  const trigger = findMentionTrigger(stateAfterChip("average ", "olist_orders", " .order_s"));

  expect(trigger?.chipTable).toBe("olist_orders");
  expect(trigger?.query).toBe("order_s");
});

test("drills the chip even when the space after it was deleted", () => {
  // The chip is inserted with a trailing space, but the user may have removed it before the
  // dot — the drill has to work either way.
  const trigger = findMentionTrigger(stateAfterChip("average ", "olist_orders", ".ord"));

  expect(trigger?.chipTable).toBe("olist_orders");
  expect(trigger?.query).toBe("ord");
});

test("does not drill a chip that is merely followed by more prose", () => {
  // A chip and then a space and a word is a finished reference, not a drill.
  expect(findMentionTrigger(stateAfterChip("rows in ", "olist_orders", " by month"))).toBeNull();
});

test("picking a column after a chip swaps the whole chip for one qualified column chip", () => {
  // The range spans the chip, so the table chip is replaced — not left beside a second chip.
  const state = stateAfterChip("average ", "olist_orders", " .order_");
  const trigger = findMentionTrigger(state)!;
  let next = state;

  insertColumnMention(trigger, trigger.chipTable!, "order_status")(state, (tr) => {
    next = state.apply(tr);
  });

  expect(draftToText(next.doc)).toBe("average olist_orders.order_status ");
  expect(next.doc.firstChild?.childCount).toBe(3); // text, columnMention, trailing space
  expect(next.doc.firstChild?.child(1).type.name).toBe("columnMention");
});

test("offers every table before anything is typed after the @", () => {
  expect(matchingTables(["events", "customers"], "")).toEqual(["events", "customers"]);
});

test("offers nothing when the menu is closed", () => {
  expect(matchingTables(["events"], undefined)).toEqual([]);
});

test("matches anywhere in the name, so a prefixed table is still findable", () => {
  // Warehouse tables carry source prefixes; typing the part the user thinks of as the name
  // has to find "northwind_orders".
  expect(matchingTables(["northwind_orders", "cars"], "orders")).toEqual(["northwind_orders"]);
});

test("puts names that start with the query ahead of names that merely contain it", () => {
  const matches = matchingTables(["northwind_order_details", "orders"], "order");
  expect(matches).toEqual(["orders", "northwind_order_details"]);
});

test("ignores case in both directions", () => {
  expect(matchingTables(["Olist_Orders"], "olist")).toEqual(["Olist_Orders"]);
});

test("keeps the menu short enough to scan", () => {
  const many = Array.from({ length: 40 }, (_, i) => `table_${i}`);
  expect(matchingTables(many, "table").length).toBe(8);
});

test("offers the whole catalog to browse before anything is typed", () => {
  // A bare "@" is the user browsing, not searching: capping it to eight hides every table
  // past the eighth (all the olist_* ones) behind a filter the user has no reason to know
  // they need. The menu scrolls, so the whole list is reachable.
  const many = Array.from({ length: 40 }, (_, i) => `table_${i}`);
  expect(matchingTables(many, "").length).toBe(40);
});
