import { expect, test } from "vitest";
import { DOMParser, DOMSerializer, type Node as ProseMirrorNode } from "prosemirror-model";

import { draftToText } from "./composerDraft";
import { columnMentionNode, composerSchema, docFromText, tableMentionNode } from "./composerSchema";

// Copying inside the composer puts the draft on the clipboard as HTML, and pasting reads it
// back. That journey runs through the schema's toDOM on the way out and parseDOM on the way
// in — so a chip only survives it if both halves agree. These go through the same DOM the
// clipboard would carry.

const { paragraph } = composerSchema.nodes;
const text = (value: string) => composerSchema.text(value);

/** Serialize a document to DOM and parse it straight back, as copy-then-paste does. */
function throughTheClipboard(doc: ProseMirrorNode): ProseMirrorNode {
  const carrier = document.createElement("div");
  carrier.appendChild(DOMSerializer.fromSchema(composerSchema).serializeFragment(doc.content));
  return DOMParser.fromSchema(composerSchema).parse(carrier);
}

test("a copied table chip pastes back as a chip", () => {
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [text("rows in "), tableMentionNode("olist_orders")]),
  ]);

  const pasted = throughTheClipboard(doc);

  expect(pasted.firstChild?.lastChild?.type.name).toBe("tableMention");
  expect(pasted.firstChild?.lastChild?.attrs.name).toBe("olist_orders");
});

test("a copied column chip pastes back still qualified by its table", () => {
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [columnMentionNode("olist_order_items", "price")]),
  ]);

  const pasted = throughTheClipboard(doc);
  const chip = pasted.firstChild?.firstChild;

  expect(chip?.type.name).toBe("columnMention");
  expect([chip?.attrs.table, chip?.attrs.name]).toEqual(["olist_order_items", "price"]);
});

test("a chip does not leave its own label behind as loose text", () => {
  // The chip renders its name as the span's text so it is readable and copyable. If parsing
  // took the node *and* its text, pasting would duplicate the identifier every time.
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [tableMentionNode("olist_orders")]),
  ]);

  expect(draftToText(throughTheClipboard(doc))).toBe("olist_orders");
});

test("a copied draft still sends exactly what it said", () => {
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [
      text("average "),
      columnMentionNode("olist_order_items", "price"),
      text(" for "),
      tableMentionNode("olist_orders"),
    ]),
  ]);

  expect(draftToText(throughTheClipboard(doc))).toBe(
    "average olist_order_items.price for olist_orders",
  );
});

test("paragraphs survive the round trip as separate blocks", () => {
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [text("first")]),
    paragraph.create(null, [text("second")]),
  ]);

  expect(draftToText(throughTheClipboard(doc))).toBe("first\n\nsecond");
});

test("a pasted line break stays a line break", () => {
  const doc = composerSchema.node("doc", null, [
    paragraph.create(null, [
      text("a"),
      composerSchema.nodes.hard_break.create(),
      text("b"),
    ]),
  ]);

  expect(draftToText(throughTheClipboard(doc))).toBe("a\nb");
});

test("an empty draft round-trips to an empty draft", () => {
  expect(draftToText(throughTheClipboard(docFromText("")))).toBe("");
});

test("a chip is one indivisible thing in the document", () => {
  // What makes Backspace remove a chip whole instead of eating it a character at a time,
  // leaving a broken identifier behind. Asserted as the schema property rather than as a
  // keystroke: deleting inside a textblock is the browser's own editing, which ProseMirror
  // then reads back — none of ProseMirror's Backspace commands fire for a plain cursor, and
  // jsdom does no native editing, so the keystroke itself is only meaningful in a browser
  // (where it is verified). This is the half we own.
  for (const chip of [composerSchema.nodes.tableMention, composerSchema.nodes.columnMention]) {
    expect(chip.isAtom).toBe(true);
    expect(chip.isLeaf).toBe(true);
  }
});
