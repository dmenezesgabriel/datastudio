import { expect, test } from "vitest";
import { Slice } from "prosemirror-model";
import { EditorState, TextSelection, type Transaction } from "prosemirror-state";
import type { EditorView } from "prosemirror-view";

import { draftToText } from "./composerDraft";
import { composerSchema, docFromText } from "./composerSchema";
import { pasteTableAsPlainText } from "./pasteTableAsPlainText";

// A stand-in for the editor holding a real document, so tests assert what the paste
// actually leaves in the draft rather than which method was called.
class RecordingView {
  state: EditorState;

  constructor(startingWith = "") {
    const doc = docFromText(startingWith);
    const opened = EditorState.create({ schema: composerSchema, doc });
    // Caret at the end, where it sits after typing — a paste lands at the selection.
    this.state = opened.apply(
      opened.tr.setSelection(TextSelection.create(doc, doc.content.size - 1)),
    );
  }

  dispatch = (transaction: Transaction): void => {
    this.state = this.state.apply(transaction);
  };

  get draft(): string {
    return draftToText(this.state.doc);
  }
}

// Stands in for a real clipboard: the same selection in several flavours, which is what a
// spreadsheet, a browser and an editor all put there.
class FakeClipboard {
  constructor(private readonly flavours: Record<string, string>) {}

  getData(type: string): string {
    return this.flavours[type] ?? "";
  }
}

function pasteOf(flavours: Record<string, string> | null): ClipboardEvent {
  const clipboardData = flavours === null ? null : new FakeClipboard(flavours);
  return { clipboardData } as unknown as ClipboardEvent;
}

function paste(view: RecordingView, event: ClipboardEvent): boolean {
  const plugin = pasteTableAsPlainText();
  // `slice` is what ProseMirror would otherwise insert — the mangled parse this handler
  // exists to pre-empt. It is never read, so an empty one stands in for it.
  const handled = plugin.props.handlePaste?.call(
    plugin,
    view as unknown as EditorView,
    event,
    Slice.empty,
  );
  return handled === true;
}

const SPREADSHEET_HTML =
  "<table><tr><td>Jan</td><td>1200</td></tr><tr><td>Feb</td><td>1450</td></tr></table>";
const SPREADSHEET_TEXT = "Jan\t1200\nFeb\t1450";

test("pastes a spreadsheet range as the text the clipboard already carries", () => {
  // This schema has no table node, so ProseMirror's parser keeps the cell text and drops
  // every boundary — "Jan1200Feb1450". The clipboard's own text/plain keeps the tabs and
  // newlines that make it readable, and is what the model can make sense of.
  const view = new RecordingView();

  const handled = paste(
    view,
    pasteOf({ "text/html": SPREADSHEET_HTML, "text/plain": SPREADSHEET_TEXT }),
  );

  expect(handled).toBe(true);
  expect(view.draft).toBe(SPREADSHEET_TEXT);
});

test("drops the pasted range where the caret is, keeping what was already typed", () => {
  const view = new RecordingView("rows: ");

  paste(view, pasteOf({ "text/html": SPREADSHEET_HTML, "text/plain": SPREADSHEET_TEXT }));

  expect(view.draft).toBe(`rows: ${SPREADSHEET_TEXT}`);
});

test("matches a table with attributes, not merely the literal tag", () => {
  const view = new RecordingView();

  paste(
    view,
    pasteOf({
      "text/html": '<table class="sheet"><tr><td>Jan</td></tr></table>',
      "text/plain": "Jan",
    }),
  );

  expect(view.draft).toBe("Jan");
});

test("leaves ordinary HTML to ProseMirror", () => {
  // Paragraphs, line breaks and our own chips all round-trip correctly through the normal
  // parser; only tabular markup has no home in this schema.
  const view = new RecordingView();

  const handled = paste(
    view,
    pasteOf({ "text/html": "<p>revenue by month</p>", "text/plain": "revenue by month" }),
  );

  expect(handled).toBe(false);
  expect(view.draft).toBe("");
});

test("does not mistake a word beginning with table for tabular markup", () => {
  const view = new RecordingView();

  const handled = paste(view, pasteOf({ "text/html": "<p>a tablet</p>", "text/plain": "a tablet" }));

  expect(handled).toBe(false);
});

test("leaves a plain-text-only paste alone", () => {
  const view = new RecordingView();

  const handled = paste(view, pasteOf({ "text/plain": "revenue by month" }));

  expect(handled).toBe(false);
  expect(view.draft).toBe("");
});

test("declines rather than swallowing a table with no plain-text flavour", () => {
  // Better the mangled paste the user can see and undo than a paste that silently does
  // nothing at all.
  const view = new RecordingView();

  const handled = paste(view, pasteOf({ "text/html": SPREADSHEET_HTML }));

  expect(handled).toBe(false);
  expect(view.draft).toBe("");
});

test("leaves an event carrying no clipboard alone", () => {
  const view = new RecordingView();

  expect(paste(view, pasteOf(null))).toBe(false);
});
