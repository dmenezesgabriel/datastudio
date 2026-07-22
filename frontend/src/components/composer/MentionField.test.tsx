import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Composer } from "../Composer";

afterEach(cleanup);

// Stands in for the schema API. Named rather than inline so each test says which tables the
// dataset has, and none of them depends on a real fetch.
class FakeSchemaApi {
  calls = 0;
  constructor(
    private readonly tables: string[],
    private readonly columnsByTable: Record<string, string[]> = {},
  ) {}

  install() {
    vi.stubGlobal("fetch", (url: string) => {
      if (!url.startsWith("/api/schema/tables")) throw new Error(`unexpected fetch: ${url}`);
      const columnsOf = /\/api\/schema\/tables\/(.+)\/columns$/.exec(url);
      if (columnsOf !== null) {
        const table = decodeURIComponent(columnsOf[1]);
        const columns = (this.columnsByTable[table] ?? []).map((name) => ({ name }));
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ table, columns }) });
      }
      this.calls += 1;
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tables: this.tables }) });
    });
  }
}

let api: FakeSchemaApi;

beforeEach(() => {
  api = new FakeSchemaApi(
    ["olist_orders", "olist_products", "northwind_order_details"],
    { olist_orders: ["order_id", "order_status", "customer_id"] },
  );
  api.install();
});

afterEach(() => vi.unstubAllGlobals());

function renderComposer(onSubmit = vi.fn()) {
  render(<Composer onSubmit={onSubmit} disabled={false} draftKey="c-1" mentionsEnabled />);
  return { field: screen.getByRole("textbox"), onSubmit };
}

// ProseMirror owns the DOM inside the editable, so drafts are typed the way a browser types:
// text goes in as a text node and the editor is told the DOM changed.
async function typeInto(field: HTMLElement, text: string) {
  // Awaited, not fired-and-forgotten: ProseMirror learns about DOM edits through a
  // MutationObserver, whose records only arrive on the next microtask.
  await act(async () => {
    field.focus();
    const paragraph = field.querySelector("p") ?? field;
    paragraph.textContent = text;
    placeCaretAtEnd(paragraph);
    fireEvent.input(field);
    await Promise.resolve();
  });
}

// Undo/redo reach ProseMirror through the editable's own keydown, so they are pressed on
// the field the way a keyboard presses them. On this platform "Mod" is Ctrl; "Shift-Mod-z"
// is the redo binding alongside "Mod-y" (editorState.ts).
async function pressUndo(field: HTMLElement) {
  await act(async () => {
    fireEvent.keyDown(field, { key: "z", ctrlKey: true });
    await Promise.resolve();
  });
}

async function pressRedo(field: HTMLElement) {
  await act(async () => {
    fireEvent.keyDown(field, { key: "z", ctrlKey: true, shiftKey: true });
    await Promise.resolve();
  });
}

function placeCaretAtEnd(node: Node) {
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(false);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
}

test("names the editable so assistive tech can announce it", () => {
  const { field } = renderComposer();
  expect(field.getAttribute("aria-multiline")).toBe("true");
  expect(screen.getByRole("textbox", { name: /ask a question about your data/i })).toBeTruthy();
});

test("loads the dataset's tables as soon as the field is focused", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
});

test("opens the table menu on @ and narrows it as the name is typed", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));

  await typeInto(field, "rows in @olist");

  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
  const options = screen.getAllByRole("option").map((option) => option.textContent);
  expect(options).toEqual(["olist_orders", "olist_products"]);
});

test("no menu until an @ is typed", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));

  await typeInto(field, "revenue by month");

  expect(screen.queryByRole("listbox")).toBeNull();
});

test("Enter picks the highlighted table instead of sending the question", async () => {
  // The menu takes precedence, exactly as claude.ai's slash menu swallows Enter while it has
  // items — otherwise choosing a table would fire off a half-written question.
  const { field, onSubmit } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  fireEvent.keyDown(field, { key: "Enter" });

  expect(onSubmit).not.toHaveBeenCalled();
  expect(field.textContent).toContain("olist_orders");
});

test("the arrows move the highlight through the menu", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  fireEvent.keyDown(field, { key: "ArrowDown" });

  const selected = screen.getAllByRole("option").find((o) => o.getAttribute("aria-selected") === "true");
  expect(selected?.textContent).toBe("olist_products");
});

test("points aria-activedescendant at the highlighted option", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  const active = field.getAttribute("aria-activedescendant");
  expect(active).toBe(screen.getAllByRole("option")[0].id);
  expect(field.getAttribute("aria-expanded")).toBe("true");
});

test("puts the highlight back on the first match when the query changes", async () => {
  // Otherwise a highlight moved down one list carries over to the next, so Enter picks a
  // table the user never looked at — and can point past the end of a shorter list.
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
  fireEvent.keyDown(field, { key: "ArrowDown" }); // highlight olist_products

  await typeInto(field, "rows in @northwind");

  await waitFor(() => expect(screen.getAllByRole("option")[0].textContent).toBe(
    "northwind_order_details",
  ));
  const selected = screen.getAllByRole("option").find((o) => o.getAttribute("aria-selected") === "true");
  expect(selected?.textContent).toBe("northwind_order_details");
});

test("keeps the highlighted option in view as the arrows move it", async () => {
  // The menu scrolls past about seven rows, so arrowing to the eighth — or wrapping from the
  // top to the bottom — would otherwise leave aria-activedescendant pointing at something
  // nobody can see. That is an accessibility defect, not a cosmetic one.
  const scrolled: (string | null)[] = [];
  vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(function (
    this: HTMLElement,
  ) {
    scrolled.push(this.textContent);
  });
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  fireEvent.keyDown(field, { key: "ArrowDown" });

  expect(scrolled.at(-1)).toBe("olist_products");
});

test("wrapping past the end brings the last option back into view", async () => {
  const scrolled: (string | null)[] = [];
  vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(function (
    this: HTMLElement,
  ) {
    scrolled.push(this.textContent);
  });
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  fireEvent.keyDown(field, { key: "ArrowUp" }); // wraps from the first to the last

  expect(scrolled.at(-1)).toBe("olist_products");
});

test("Escape closes the menu and leaves the draft alone", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  fireEvent.keyDown(field, { key: "Escape" });

  expect(screen.queryByRole("listbox")).toBeNull();
  expect(field.textContent).toContain("@olist"); // the typed text survives the dismissal
});

test("sends the bare table name, not the @ the user typed", async () => {
  // The whole reason the chip exists: text2SQL receives an identifier the engine has.
  const { field, onSubmit } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
  fireEvent.keyDown(field, { key: "Enter" }); // picks olist_orders

  fireEvent.keyDown(field, { key: "Enter" }); // menu closed → sends

  expect(onSubmit).toHaveBeenCalledWith("rows in olist_orders");
});

test("Enter sends when no menu is open", async () => {
  const { field, onSubmit } = renderComposer();
  await typeInto(field, "revenue by month");

  fireEvent.keyDown(field, { key: "Enter" });

  expect(onSubmit).toHaveBeenCalledWith("revenue by month");
});

test("does not send on the Enter that confirms an IME candidate", async () => {
  const { field, onSubmit } = renderComposer();
  await typeInto(field, "売上");

  fireEvent.keyDown(field, { key: "Enter", isComposing: true });

  expect(onSubmit).not.toHaveBeenCalled();
});

test("keeps a chip when the draft is stored and reopened", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "rows in @olist");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
  fireEvent.keyDown(field, { key: "Enter" });
  cleanup();

  render(<Composer onSubmit={vi.fn()} disabled={false} draftKey="c-1" mentionsEnabled />);

  expect(screen.getByRole("textbox").querySelector("[data-table-mention]")?.textContent).toBe(
    "olist_orders",
  );
});

test("a dot on a highlighted table drills into its columns", async () => {
  // Reaching a column must not mean typing the table's full name by hand — that is what
  // the menu exists to avoid.
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "average @olist_ord");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  await act(async () => {
    fireEvent.keyDown(field, { key: "." });
    await Promise.resolve();
  });

  await waitFor(() =>
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "order_id",
      "order_status",
      "customer_id",
    ]),
  );
});

test("narrows the columns as the name after the dot is typed", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));

  await typeInto(field, "average @olist_orders.order_s");

  await waitFor(() =>
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["order_status"]),
  );
});

test("sends a picked column qualified by its table", async () => {
  // The point of the column chip: "order_id" alone is ambiguous across six tables.
  const { field, onSubmit } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "average @olist_orders.order_s");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
  fireEvent.keyDown(field, { key: "Enter" }); // picks order_status

  fireEvent.keyDown(field, { key: "Enter" }); // menu closed -> sends

  expect(onSubmit).toHaveBeenCalledWith("average olist_orders.order_status");
});

test("offers no menu for a dot after something that is not a table", async () => {
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));

  await typeInto(field, "@not_a_table.");

  expect(screen.queryByRole("listbox")).toBeNull();
});

test("Ctrl+Z undoes the user's typing, Ctrl+Shift+Z brings it back", async () => {
  const { field } = renderComposer();
  await typeInto(field, "revenue by month");

  await pressUndo(field);
  expect(field.textContent).not.toContain("revenue by month");

  await pressRedo(field);
  expect(field.textContent).toContain("revenue by month");
});

test("switching threads gives thread B a fresh undo history isolated from thread A", async () => {
  // Switching threads reloads a different draft — a context switch, not an edit. showDoc
  // rebuilds the editor state so thread B gets a clean history: B's own edits undo, and no
  // amount of Ctrl+Z reaches back into thread A's draft. Recording the swap instead would
  // let Ctrl+Z resurrect A; merely suppressing it (addToHistory: false) would leave A's edit
  // lingering on the stack for a later Ctrl+Z to pull in, and break B's own undo once its
  // steps were mapped through the swap. The 600ms wait keeps the typing and the swap in
  // separate history groups — real usage, where the swap comes long after the typing — so a
  // recorded swap is independently undoable and the isolation is genuinely exercised.
  const onSubmit = vi.fn();
  const { rerender } = render(
    <Composer onSubmit={onSubmit} disabled={false} draftKey="undo-thread-a" mentionsEnabled />,
  );
  const field = screen.getByRole("textbox");
  await typeInto(field, "draft that lives in thread A");
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 600));
  });

  // Re-point the same composer at another thread in place (not a remount), so the swap runs.
  rerender(<Composer onSubmit={onSubmit} disabled={false} draftKey="undo-thread-b" mentionsEnabled />);
  await waitFor(() => expect(field.textContent).not.toContain("draft that lives in thread A"));
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 600)); // keep B's edit its own history group
  });

  // B's own edit is undoable on its fresh history…
  await typeInto(field, "an edit made in thread B");
  await pressUndo(field);
  expect(field.textContent).not.toContain("an edit made in thread B");

  // …and undoing past it never pulls thread A's draft into thread B (a recorded swap would
  // surface A here; a fresh history has nothing of A's to reach).
  await pressUndo(field);
  expect(field.textContent).not.toContain("draft that lives in thread A");
});

test("a dot typed in the column menu stays an ordinary character", async () => {
  // Only the table menu claims "."; in the column menu it has to reach the document, since
  // a column name may contain one.
  const { field } = renderComposer();
  act(() => field.focus());
  await waitFor(() => expect(api.calls).toBe(1));
  await typeInto(field, "@olist_orders.order");
  await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());

  const claimed = !fireEvent.keyDown(field, { key: "." });

  expect(claimed).toBe(false);
});
