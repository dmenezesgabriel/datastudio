import { baseKeymap, splitBlock } from "prosemirror-commands";
import { history, redo, undo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { type Node as ProseMirrorNode } from "prosemirror-model";
import { type Command, EditorState } from "prosemirror-state";

import { pasteTableAsPlainText } from "./pasteTableAsPlainText";
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
      keymap({
        "Mod-z": claimHistoryKey(undo),
        "Shift-Mod-z": claimHistoryKey(redo),
        "Mod-y": claimHistoryKey(redo),
      }),
      keymap(baseKeymap),
      history(),
      placeholderPlugin(placeholder),
      // Ahead of nothing in particular, but it has to be a plugin rather than a prop so it
      // sits with the rest of the editor's behaviour: a pasted spreadsheet range would
      // otherwise lose every cell and row boundary on the way in.
      pasteTableAsPlainText(),
    ],
  });
}

/**
 * Wrap an undo/redo command so its key is always claimed, empty stack or not.
 *
 * undo and redo report false when there is nothing to do, and prosemirror-keymap then lets
 * the keypress fall through to the browser's own contentEditable history — which edits the
 * document out from under ProseMirror (Ctrl+Shift+Z on an empty redo stack was toggling the
 * last change). The editor owns these keys, so it claims them whether or not the stack had
 * anything: run the command, then swallow the key regardless.
 *
 * Example:
 *     keymap({ "Mod-z": claimHistoryKey(undo) })
 */
function claimHistoryKey(command: Command): Command {
  return (state, dispatch, view) => {
    command(state, dispatch, view);
    return true;
  };
}
