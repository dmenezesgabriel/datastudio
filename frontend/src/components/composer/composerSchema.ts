import { type Node as ProseMirrorNode, Schema } from "prosemirror-model";

// The composer's document shape. Deliberately tiny: a question is plain text plus the
// entities it names, so there is no bold, no headings, no lists — the model is sent text,
// and formatting marks would only be silently discarded on the way out. This is the same
// four-node shape ChatGPT's composer ships (doc / paragraph / text / hard_break), with one
// atom of our own for a referenced table.
export const composerSchema = new Schema({
  nodes: {
    doc: { content: "block+" },

    paragraph: {
      content: "inline*",
      group: "block",
      // preserveWhitespace: pasting a query or a column of figures must keep its spacing
      // rather than collapsing to single spaces.
      parseDOM: [{ tag: "p", preserveWhitespace: "full" }],
      toDOM: () => ["p", 0],
    },

    text: { group: "inline" },

    // Only ever arrives by pasting HTML that contains a <br> — Shift+Enter splits the
    // paragraph instead. leafText is what keeps it from vanishing when the draft is
    // flattened to the text that gets sent.
    hard_break: {
      inline: true,
      group: "inline",
      selectable: false,
      leafText: () => "\n",
      parseDOM: [{ tag: "br" }],
      toDOM: () => ["br"],
    },

    // A table the question refers to, held as one indivisible unit: the user picked it from
    // the real schema, so it should not be editable into something the engine does not have.
    // leafText is the payload — it puts the bare identifier into the text the model reads,
    // which is the entire reason the chip is worth its complexity.
    tableMention: {
      inline: true,
      group: "inline",
      atom: true,
      selectable: false,
      attrs: { name: {} },
      leafText: (node) => String(node.attrs.name),
      parseDOM: [
        {
          tag: "span[data-table-mention]",
          getAttrs: (dom: HTMLElement) => ({ name: dom.getAttribute("data-table-mention") ?? "" }),
        },
      ],
      toDOM: (node) => [
        "span",
        { "data-table-mention": String(node.attrs.name), class: "composer__mention" },
        String(node.attrs.name),
      ],
    },

    // A column of a named table. Held qualified — the column name alone is ambiguous
    // across tables, and "order_id" in six tables is exactly the ambiguity the chip
    // exists to remove. leafText emits "table.column", which is how SQL names it too.
    columnMention: {
      inline: true,
      group: "inline",
      atom: true,
      selectable: false,
      attrs: { table: {}, name: {} },
      leafText: (node) => `${String(node.attrs.table)}.${String(node.attrs.name)}`,
      parseDOM: [
        {
          tag: "span[data-column-mention]",
          getAttrs: (dom: HTMLElement) => ({
            table: dom.getAttribute("data-column-table") ?? "",
            name: dom.getAttribute("data-column-mention") ?? "",
          }),
        },
      ],
      toDOM: (node) => [
        "span",
        {
          "data-column-mention": String(node.attrs.name),
          "data-column-table": String(node.attrs.table),
          class: "composer__mention",
        },
        `${String(node.attrs.table)}.${String(node.attrs.name)}`,
      ],
    },
  },
  // No marks at all: nothing in a question survives as formatting, so the schema should not
  // pretend otherwise (a mark the serializer drops is a lie to whoever applied it).
  marks: {},
});

/**
 * Build a table chip for `name`.
 *
 * Example:
 *     tableMentionNode("events")
 */
export function tableMentionNode(name: string): ProseMirrorNode {
  return composerSchema.nodes.tableMention.create({ name });
}

/**
 * Build a column chip for `name` on `table`.
 *
 * Example:
 *     columnMentionNode("events", "amount")
 */
export function columnMentionNode(table: string, name: string): ProseMirrorNode {
  return composerSchema.nodes.columnMention.create({ table, name });
}

/**
 * Build a single-paragraph document holding `text` — an empty string gives an empty composer.
 *
 * Example:
 *     docFromText("revenue by month")
 */
export function docFromText(text: string): ProseMirrorNode {
  const content = text === "" ? [] : [composerSchema.text(text)];
  return composerSchema.node("doc", null, [composerSchema.node("paragraph", null, content)]);
}
