import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Composer } from "../Composer";

afterEach(cleanup);

// Stands in for the schema API. Named rather than inline so each test says which tables the
// dataset has, and none of them depends on a real fetch.
class FakeSchemaApi {
  calls = 0;
  constructor(private readonly tables: string[]) {}

  install() {
    vi.stubGlobal("fetch", (url: string) => {
      if (!url.startsWith("/api/schema/tables")) throw new Error(`unexpected fetch: ${url}`);
      this.calls += 1;
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tables: this.tables }) });
    });
  }
}

let api: FakeSchemaApi;

beforeEach(() => {
  api = new FakeSchemaApi(["olist_orders", "olist_products", "northwind_order_details"]);
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
