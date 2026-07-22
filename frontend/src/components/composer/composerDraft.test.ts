import { expect, test } from "vitest";

import {
  columnMentionNode,
  composerSchema,
  docFromText,
  tableMentionNode,
} from "./composerSchema";
import { draftFromStorage, draftToStorage, draftToText } from "./composerDraft";

const { paragraph, hard_break: hardBreak } = composerSchema.nodes;
const text = (value: string) => composerSchema.text(value);

test("sends a plain question as its own text", () => {
  const doc = docFromText("revenue by month");
  expect(draftToText(doc)).toBe("revenue by month");
});

test("sends a table chip as the bare identifier the engine knows", () => {
  // The whole point of the chip: the model receives a verified table name instead of
  // whatever prose the user typed around it. No "@", no markup — just the identifier.
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [
      text("rows in "),
      tableMentionNode("olist_orders"),
      text(" last month"),
    ]),
  ]);

  expect(draftToText(doc)).toBe("rows in olist_orders last month");
});

test("separates paragraphs with a blank line", () => {
  // Shift+Enter splits the block rather than inserting a <br>, so multi-line questions are
  // paragraphs — they have to reach the model as separated text, not run together.
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [text("first")]),
    paragraph.create(null, [text("second")]),
  ]);

  expect(draftToText(doc)).toBe("first\n\nsecond");
});

test("turns a pasted line break into a newline", () => {
  // hard_break only ever arrives by pasting HTML containing <br>; it must not vanish.
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [text("a"), hardBreak.create(), text("b")]),
  ]);

  expect(draftToText(doc)).toBe("a\nb");
});

test("an untouched composer sends nothing", () => {
  expect(draftToText(docFromText(""))).toBe("");
});

test("reads back a draft left by the plain-text composer", () => {
  // Drafts written before the composer stored documents are still in storage. Reading one
  // as text keeps a half-written question through the upgrade instead of dropping it.
  expect(draftToText(draftFromStorage("revenue by month"))).toBe("revenue by month");
});

test("falls back to text rather than throwing on a corrupt draft", () => {
  // A truncated or hand-edited entry must not stop the composer from mounting.
  expect(draftToText(draftFromStorage('{"type":"doc",'))).toBe('{"type":"doc",');
});

test("an absent draft opens an empty composer", () => {
  expect(draftToText(draftFromStorage(""))).toBe("");
});

test("a chip survives being stored and reopened", () => {
  // Drafts are parked as the document itself, so reopening a thread brings the chip back as
  // a chip — storing the flattened text would silently demote it to prose.
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [text("rows in "), tableMentionNode("olist_orders")]),
  ]);

  const reopened = draftFromStorage(draftToStorage(doc));

  expect(reopened.firstChild?.lastChild?.type.name).toBe("tableMention");
  expect(draftToText(reopened)).toBe("rows in olist_orders");
});

test("sends a column chip qualified by its table", () => {
  // "order_id" alone appears in six tables; the qualified name is the whole reason the
  // column chip is worth having, and it is how SQL names a column too.
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [
      text("average "),
      columnMentionNode("olist_order_items", "price"),
      text(" per order"),
    ]),
  ]);

  expect(draftToText(doc)).toBe("average olist_order_items.price per order");
});

test("a column chip survives being stored and reopened", () => {
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [columnMentionNode("events", "amount")]),
  ]);

  const reopened = draftFromStorage(draftToStorage(doc));

  expect(reopened.firstChild?.firstChild?.type.name).toBe("columnMention");
  expect(draftToText(reopened)).toBe("events.amount");
});
