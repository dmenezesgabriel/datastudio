import { expect, test } from "vitest";
import { EditorState, TextSelection } from "prosemirror-state";

import { composerSchema, docFromText, tableMentionNode } from "./composerSchema";
import { findMentionTrigger, insertTableMention, matchingTables } from "./tableMention";
import { draftToText } from "./composerDraft";

// A state holding `text` with the caret parked at its end — what the composer looks like
// mid-typing, which is the only moment the trigger matters.
function stateTyping(text: string): EditorState {
  const state = EditorState.create({ schema: composerSchema, doc: docFromText(text) });
  const end = state.doc.content.size - 1; // inside the paragraph, after its last character
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
