import { baseKeymap, splitBlock } from "prosemirror-commands";
import { history, redo, undo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { type Node as ProseMirrorNode } from "prosemirror-model";
import { EditorState } from "prosemirror-state";

import { placeholderPlugin } from "./placeholderPlugin";

/**
 * The composer's editor state: the draft document and the behaviour wrapped around it.
 *
 * Example:
 *     buildEditorState(docFromText("revenue by month"), "Ask a question…")
 */
export function buildEditorState(doc: ProseMirrorNode, placeholder: string): EditorState {
  return EditorState.create({
    doc,
    plugins: [
      // Shift+Enter (and Alt+Enter) start a new paragraph rather than inserting a line
      // break — the override both claude.ai and ChatGPT apply to their editors, so a
      // multi-line question reaches the model as separated text rather than one run-on line.
      // Bound ahead of the base keymap, which would otherwise claim Enter first.
      keymap({ "Shift-Enter": splitBlock, "Alt-Enter": splitBlock }),
      keymap({ "Mod-z": undo, "Shift-Mod-z": redo, "Mod-y": redo }),
      keymap(baseKeymap),
      history(),
      placeholderPlugin(placeholder),
    ],
  });
}
