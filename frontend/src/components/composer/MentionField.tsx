import {
  type KeyboardEvent,
  type RefObject,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { type Node as ProseMirrorNode } from "prosemirror-model";
import { EditorState } from "prosemirror-state";
import { EditorView } from "prosemirror-view";

import { useDraft } from "../../hooks/useDraft";
import { useSchemaTables } from "../../hooks/useSchemaTables";
import { MentionMenu, optionId } from "./MentionMenu";
import { draftFromStorage, draftToStorage, draftToText } from "./composerDraft";
import { docFromText } from "./composerSchema";
import type { ComposerFieldHandle } from "./composerField";
import { buildEditorState } from "./editorState";
import { useTableColumns } from "../../hooks/useTableColumns";
import { type MentionQuery, matchingColumns, parseMentionQuery } from "./mentionQuery";
import {
  type MentionTrigger,
  findMentionTrigger,
  insertColumnMention,
  insertTableMention,
  matchingTables,
  typeMentionQuery,
} from "./tableMention";

const MENU_ID = "composer-table-menu";
// Keys the open menu claims. Enter picks the highlighted table instead of sending the
// question, and the arrows move the highlight instead of the caret — the same precedence
// claude.ai gives its slash menu.
const MENU_KEYS = ["Enter", "Tab", "ArrowUp", "ArrowDown", "Escape"];
// Keys that drill a highlighted table into its columns. "." is the primary gesture; "→" is
// the familiar tree-view alias. Both are claimed only while the menu is showing tables — in
// the column menu "." is an ordinary character (a column name may contain one) and "→" is an
// ordinary caret move.
const DRILL_KEYS = [".", "ArrowRight"];

// The composer's structured editing surface: text, plus chips standing for real tables.
// A ProseMirror document rather than a string, because a chip has to stay one indivisible
// thing carrying an identifier the engine actually has — the same name typed as prose leaves
// the model to work out which table was meant.
export function MentionField({
  ref,
  draftKey,
  placeholder,
  autoFocus,
  onEnter,
}: {
  ref: RefObject<ComposerFieldHandle | null>;
  draftKey: string;
  placeholder: string;
  autoFocus: boolean;
  /** Enter pressed on a draft that should be sent — the shell decides what that means. */
  onEnter: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const { text: stored, setText: storeDraft, clearText } = useDraft(draftKey);
  const { tables, load: loadTables } = useSchemaTables();
  const [trigger, setTrigger] = useState<MentionTrigger | null>(null);
  const [highlighted, setHighlighted] = useState(0);
  // Escape shuts the menu without touching the draft, so the "@" the user typed is still
  // there. Remembering where it was is what stops the menu reopening on the next keystroke.
  const [dismissedAt, setDismissedAt] = useState<number | null>(null);

  const view = useEditorView({ host, placeholder, autoFocus, stored, storeDraft, setTrigger });

  // What the "@" is turning into: a table until a dot follows one, its columns after. A
  // trigger drilled from a chip already names its table, so it goes straight to that table's
  // columns without re-parsing a "table." that is not in the text.
  const mention = useMemo<MentionQuery | null>(() => {
    if (trigger === null) return null;
    if (trigger.chipTable !== undefined)
      return { kind: "column", table: trigger.chipTable, query: trigger.query };
    return parseMentionQuery(trigger.query, tables);
  }, [trigger, tables]);
  const columns = useTableColumns(mention?.kind === "column" ? mention.table : null);
  const matches = useMemo(
    () =>
      mention === null
        ? []
        : mention.kind === "table"
          ? matchingTables(tables, mention.query)
          : matchingColumns(columns, mention.query),
    [mention, tables, columns],
  );
  const isOpen = trigger !== null && trigger.from !== dismissedAt && matches.length > 0;

  // A highlight belongs to the list it was moved through. Editing the query builds a new
  // list, so it starts again at the top — otherwise Enter picks a table the user never
  // looked at, and the index can point past the end of a list that has since got shorter.
  useEffect(() => setHighlighted(0), [trigger?.query]);

  useSwapDraftOnKeyChange(view, draftKey, stored);
  useComboboxState(view, isOpen ? MENU_ID : null, highlighted);

  useImperativeHandle(
    ref,
    () => ({
      readText: () => (view.current ? draftToText(view.current.state.doc) : ""),
      clear: () => {
        clearText();
        showDoc(view.current, docFromText(""));
      },
      restore: (text) => showDoc(view.current, docFromText(text)),
    }),
    [view, clearText],
  );

  /** Put the highlighted name into the draft as a chip. */
  function pick(name: string) {
    const editor = view.current;
    if (editor === null || trigger === null || mention === null) return;
    const insert =
      mention.kind === "table"
        ? insertTableMention(trigger, name)
        : insertColumnMention(trigger, mention.table, name);
    insert(editor.state, editor.dispatch);
    editor.focus();
  }

  /** Carry a table into its columns, so "." (or the chevron) drills in instead of picking. */
  function drillIntoTable(name: string = matches[highlighted]) {
    const editor = view.current;
    if (editor === null || trigger === null) return;
    typeMentionQuery(trigger, `${name}.`)(editor.state, editor.dispatch);
    editor.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    // Mid-composition, Enter accepts the IME's candidate rather than ending the message —
    // sending here fires mid-word for anyone typing Japanese, Chinese, or Korean.
    if (event.nativeEvent.isComposing) return;
    const claimed =
      MENU_KEYS.includes(event.key) ||
      (DRILL_KEYS.includes(event.key) && mention?.kind === "table");
    if (isOpen && claimed) return claimForMenu(event);
    if (event.key === "Enter" && !event.shiftKey && !event.altKey) {
      // Shift+Enter and Alt+Enter fall through to the editor, which splits the paragraph.
      event.preventDefault();
      onEnter();
    }
  }

  // Captured, not bubbled: ProseMirror listens on the editable itself, so a bubbling handler
  // would run after the document had already acted on the key.
  function claimForMenu(event: KeyboardEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (event.key === "Escape") return setDismissedAt(trigger?.from ?? null);
    if (event.key === "ArrowDown") return setHighlighted(step(highlighted, 1, matches.length));
    if (event.key === "ArrowUp") return setHighlighted(step(highlighted, -1, matches.length));
    // "." or "→" on a highlighted table means "now show me its columns" — otherwise the only
    // way to reach a column would be to type the table's full name by hand, which is exactly
    // what the menu exists to avoid.
    if (DRILL_KEYS.includes(event.key)) return drillIntoTable();
    pick(matches[highlighted]);
  }

  return (
    <div className="composer__editor" onFocus={loadTables} onKeyDownCapture={handleKeyDown}>
      {isOpen && mention !== null && (
        <MentionMenu
          id={MENU_ID}
          label={menuLabel(mention)}
          hint={menuHint(mention)}
          matches={matches}
          highlighted={highlighted}
          onPick={pick}
          // Only tables drill; the chevron is absent in the column menu, where there is
          // nothing further to open.
          onDrill={mention.kind === "table" ? drillIntoTable : undefined}
        />
      )}
      {/* ProseMirror owns everything inside this element. React must never render children
          into it, and must never move it: re-attaching a contenteditable drops the caret,
          which is why the host is a plain ref rather than a callback ref. */}
      <div ref={host} className="composer__input w-full text-base p-3" />
    </div>
  );
}

/** Build the editor once, into `host`, and keep it alive for the life of the field. */
function useEditorView({
  host,
  placeholder,
  autoFocus,
  stored,
  storeDraft,
  setTrigger,
}: {
  host: RefObject<HTMLDivElement | null>;
  placeholder: string;
  autoFocus: boolean;
  stored: string;
  storeDraft: (text: string) => void;
  setTrigger: (trigger: MentionTrigger | null) => void;
}): RefObject<EditorView | null> {
  const view = useRef<EditorView | null>(null);
  // The editor outlives every render; reaching the current callbacks through a ref is what
  // lets it stay built instead of being torn down whenever one of them changes identity.
  const latest = useRef({ storeDraft, setTrigger });
  latest.current = { storeDraft, setTrigger };
  // Read once: re-reading the stored draft each render would fight the editor for control
  // of its own document.
  const opening = useRef(stored);

  useEffect(() => {
    if (host.current === null) return;
    // Named so the transaction handler can reach the editor it belongs to; `this` is typed
    // as the props object there, not the view.
    const editor: EditorView = new EditorView(host.current, {
      state: buildEditorState(draftFromStorage(opening.current), placeholder),
      attributes: {
        // Without these a contenteditable is an anonymous box to assistive tech: this names
        // it, announces it as a multi-line field, and says it drives a list of suggestions.
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": placeholder,
        "aria-autocomplete": "list",
      },
      dispatchTransaction(transaction) {
        const next = editor.state.apply(transaction);
        editor.updateState(next);
        if (transaction.docChanged) latest.current.storeDraft(draftToStorage(next.doc));
        latest.current.setTrigger(findMentionTrigger(next));
      },
    });

    view.current = editor;
    if (autoFocus) editor.focus();
    return () => {
      editor.destroy();
      view.current = null;
    };
    // Built once per mount: placeholder and autoFocus are read at construction and do not
    // change for a mounted composer, and everything mutable is reached through refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return view;
}

/** Show this thread's own draft when the composer is pointed at another conversation. */
function useSwapDraftOnKeyChange(
  view: RefObject<EditorView | null>,
  draftKey: string,
  stored: string,
): void {
  const shown = useRef(draftKey);
  const latestStored = useRef(stored);
  latestStored.current = stored;

  useEffect(() => {
    if (shown.current === draftKey) return;
    shown.current = draftKey;
    showDoc(view.current, draftFromStorage(latestStored.current));
  }, [draftKey, view]);
}

/** Keep the editable's combobox attributes pointed at the open menu and its highlight. */
function useComboboxState(
  view: RefObject<EditorView | null>,
  openMenuId: string | null,
  highlighted: number,
): void {
  useEffect(() => {
    const dom = view.current?.dom;
    if (dom === undefined) return;
    dom.setAttribute("aria-expanded", String(openMenuId !== null));
    setOrRemove(dom, "aria-controls", openMenuId);
    setOrRemove(dom, "aria-activedescendant", openMenuId && optionId(openMenuId, highlighted));
  }, [view, openMenuId, highlighted]);
}

function setOrRemove(dom: Element, name: string, value: string | null): void {
  if (value === null) dom.removeAttribute(name);
  else dom.setAttribute(name, value);
}

/** What the menu announces to assistive tech: which list it is showing. */
function menuLabel(mention: MentionQuery): string {
  return mention.kind === "table" ? "Tables" : `Columns of ${mention.table}`;
}

/** The one-line affordance under the menu, telling the user the drill exists. */
function menuHint(mention: MentionQuery): string {
  return mention.kind === "table" ? "↵ add · . or → for columns" : "↵ add column";
}

/** Move the highlight, wrapping at both ends so the list is a loop. */
function step(current: number, by: number, length: number): number {
  return (current + by + length) % length;
}

/** Swap the whole document — a new draft, a sent question, or a failed send put back. */
function showDoc(view: EditorView | null, doc: ProseMirrorNode): void {
  if (view === null) return;
  // Loading another draft is a context switch, not an edit, so it gets a fresh editor state:
  // the same plugins over the new document, with an empty undo history. Replacing the doc
  // with a transaction instead couples every draft to one shared history — recorded, Ctrl+Z
  // resurrects the previous draft; suppressed (addToHistory: false), that draft's edits still
  // linger on the stack and stay harmless only because ProseMirror maps them to no-ops, a
  // fragile guarantee to lean on. A fresh state scopes undo to the draft on screen outright.
  view.updateState(EditorState.create({ doc, plugins: view.state.plugins }));
}
