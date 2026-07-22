import { Plugin } from "prosemirror-state";

// Pasting a range out of a spreadsheet is a routine thing to do in a BI tool, and this
// schema has no table node to put it in. ProseMirror's parser therefore keeps the cell text
// and drops every <table>/<tr>/<td> around it, so
//
//     <table><tr><td>Jan</td><td>1200</td></tr><tr><td>Feb</td><td>1450</td></tr></table>
//
// arrives as "Jan1200Feb1450" — one paragraph, every boundary gone. The same clipboard
// always carries a text/plain flavour of the same selection ("Jan\t1200\nFeb\t1450"), which
// is both readable and what the model can make sense of, so tabular HTML is served from
// there instead. claude.ai does exactly this, for exactly this reason.
//
// The text is inserted directly rather than handed back to view.pasteText: doPaste consults
// handlePaste *before* it inserts anything, so routing through it would re-enter this very
// handler with the same clipboard still on the event, and recurse until the stack gave out.

// Matches an opening <table> tag proper — the trailing [\s>] is what keeps a word like
// "tablet" in pasted prose from being read as markup.
const TABULAR_HTML = /<table[\s>]/i;

/**
 * Insert tabular HTML as the clipboard's own plain text, since this schema cannot hold it.
 *
 * Example:
 *     buildEditorState(doc, placeholder) // registers it alongside the other plugins
 */
export function pasteTableAsPlainText(): Plugin {
  return new Plugin({
    props: {
      handlePaste(view, event) {
        const clipboard = event.clipboardData;
        if (clipboard === null) return false;
        if (!TABULAR_HTML.test(clipboard.getData("text/html"))) return false;

        const text = clipboard.getData("text/plain");
        // No plain-text flavour to fall back on: let ProseMirror do its mangled best rather
        // than swallow the paste, so the user sees something they can undo.
        if (text === "") return false;

        // Tabs and newlines are kept as they were copied — the field renders them
        // (.composer__input .ProseMirror is pre-wrap) and the draft sends the range exactly
        // as the spreadsheet had it.
        view.dispatch(view.state.tr.insertText(text).scrollIntoView());
        return true;
      },
    },
  });
}
