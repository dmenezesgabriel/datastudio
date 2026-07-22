import { Plugin } from "prosemirror-state";
import { Decoration, DecorationSet } from "prosemirror-view";

// A contenteditable has no placeholder of its own, so the prompt is drawn as a decoration
// over the empty paragraph. A decoration and not real content: placeholder text that lived
// in the document would be serialized and sent as the question.

/**
 * Show `text` while the draft is empty.
 *
 * Example:
 *     placeholderPlugin("Ask a question about your data…")
 */
export function placeholderPlugin(text: string): Plugin {
  return new Plugin({
    props: {
      decorations(state) {
        const { doc } = state;
        const firstBlock = doc.firstChild;
        const isEmpty = doc.childCount === 1 && firstBlock !== null && firstBlock.content.size === 0;
        if (!isEmpty) return DecorationSet.empty;
        return DecorationSet.create(doc, [
          Decoration.node(0, firstBlock.nodeSize, {
            class: "composer__placeholder",
            "data-placeholder": text,
          }),
        ]);
      },
    },
  });
}
