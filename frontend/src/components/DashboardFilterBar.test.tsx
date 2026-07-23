import type { Spec } from "@json-render/react";
import { JSONUIProvider } from "@json-render/react";
import { afterEach, describe, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import { DashboardFilterBar } from "./DashboardFilterBar";
import { registry } from "../registry";
import type { SpecWithState } from "../types";

afterEach(cleanup);

// Category (2 values → chip group, shared by chart+table) and Product (9 values → popover).
const PRODUCTS = ["Chai", "Chang", "Cola", "Water", "Juice", "Milk", "Cream", "Butter", "Cheese"];
function dashboard(): SpecWithState {
  return {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["c", "t"] },
      c: {
        type: "ChartJs",
        props: { kind: "bar", title: "x", labelColumn: "category", valueColumns: ["total"], data: { $state: "/w0/rows" } },
        children: [],
      },
      t: { type: "DataTable", props: { data: { $state: "/w1" } }, children: [] },
    },
    state: {
      w0: { columns: ["category", "total"], rows: [{ category: "Beverages", total: 5 }, { category: "Dairy", total: 3 }] },
      w1: {
        columns: ["product", "category"],
        rows: PRODUCTS.map((product, i) => ({ product, category: i < 5 ? "Beverages" : "Dairy" })),
      },
    },
  };
}

function renderBar(spec: SpecWithState) {
  return render(
    <JSONUIProvider registry={registry} initialState={spec.state ?? {}}>
      <DashboardFilterBar spec={spec as Spec} />
    </JSONUIProvider>,
  );
}

/** Open the Product multi-select popover and return a scoped query for its dialog. */
function openProduct() {
  fireEvent.click(screen.getByRole("button", { name: /^product:/i }));
  return within(screen.getByRole("dialog", { name: /product filter/i }));
}

describe("DashboardFilterBar", () => {
  test("renders nothing when the dashboard has no filterable dimensions", () => {
    const textOnly: SpecWithState = {
      root: "root",
      elements: { root: { type: "Stack", props: {}, children: ["m"] }, m: { type: "Markdown", props: { text: "hi" }, children: [] } },
      state: {},
    };
    const { container } = renderBar(textOnly);
    expect(container.textContent).toBe("");
  });

  test("shows a chip group for a low-cardinality dimension and a popover trigger for a high-cardinality one", () => {
    renderBar(dashboard());
    expect(screen.getByRole("button", { name: "Beverages" })).toBeTruthy(); // category → chips
    // product → a disclosure button summarising the selection, not a native single-select.
    const trigger = screen.getByRole("button", { name: /^product:/i });
    expect(trigger.getAttribute("aria-haspopup")).toBe("dialog");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  test("selecting a chip activates that filter (aria-pressed) and shows a removable active chip", () => {
    renderBar(dashboard());
    fireEvent.click(screen.getByRole("button", { name: "Beverages" }));
    expect(screen.getByRole("button", { name: "Beverages" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /remove filter.*category.*beverages/i })).toBeTruthy();
  });

  test("a chip group is multi-select: two values stay active at once (OR within the field)", () => {
    renderBar(dashboard());
    fireEvent.click(screen.getByRole("button", { name: "Beverages" }));
    fireEvent.click(screen.getByRole("button", { name: "Dairy" }));
    expect(screen.getByRole("button", { name: "Beverages" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Dairy" }).getAttribute("aria-pressed")).toBe("true");
    // One removable active chip per value.
    expect(screen.getByRole("button", { name: /remove filter.*category.*beverages/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /remove filter.*category.*dairy/i })).toBeTruthy();
  });

  test("the popover searches its options and multi-selects with checkboxes, committing on Apply", () => {
    renderBar(dashboard());
    const dialog = openProduct();
    // Search narrows the checkbox list by display text.
    fireEvent.change(dialog.getByRole("searchbox", { name: /search product/i }), { target: { value: "ch" } });
    expect(dialog.getByRole("checkbox", { name: "Chai" })).toBeTruthy();
    expect(dialog.getByRole("checkbox", { name: "Cheese" })).toBeTruthy();
    expect(dialog.queryByRole("checkbox", { name: "Cola" })).toBeNull();
    // Ticking stages a draft — the filter has NOT run yet (safety: the trigger still reads "All").
    fireEvent.click(dialog.getByRole("checkbox", { name: "Chai" }));
    fireEvent.click(dialog.getByRole("checkbox", { name: "Cheese" }));
    expect(screen.getByRole("button", { name: /^product: all/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /remove filter.*product/i })).toBeNull();
    // Apply commits the draft: the trigger summarises the count and each value is a removable chip.
    fireEvent.click(dialog.getByRole("button", { name: /^apply$/i }));
    expect(screen.getByRole("button", { name: /^product: 2 selected/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /remove filter.*product.*chai/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /remove filter.*product.*cheese/i })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull(); // Apply closes the panel
  });

  test("Escape discards the staged draft without running the filter", () => {
    renderBar(dashboard());
    const dialog = openProduct();
    fireEvent.click(dialog.getByRole("checkbox", { name: "Water" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    // Nothing was applied — the dimension is still unfiltered.
    expect(screen.getByRole("button", { name: /^product: all/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /remove filter.*product/i })).toBeNull();
  });

  test("the popover 'Clear' empties the draft, applied on Apply", () => {
    renderBar(dashboard());
    // Seed a committed selection, then reopen and clear it.
    let dialog = openProduct();
    fireEvent.click(dialog.getByRole("checkbox", { name: "Water" }));
    fireEvent.click(dialog.getByRole("button", { name: /^apply$/i }));
    expect(screen.getByRole("button", { name: /^product: water/i })).toBeTruthy();
    dialog = openProduct();
    fireEvent.click(dialog.getByRole("button", { name: /^clear$/i }));
    fireEvent.click(dialog.getByRole("button", { name: /^apply$/i }));
    expect(screen.getByRole("button", { name: /^product: all/i })).toBeTruthy();
  });

  test("two dimensions compose (AND): both stay active, and Clear all resets them", () => {
    renderBar(dashboard());
    fireEvent.click(screen.getByRole("button", { name: "Beverages" }));
    const dialog = openProduct();
    fireEvent.click(dialog.getByRole("checkbox", { name: "Chai" }));
    fireEvent.click(dialog.getByRole("button", { name: /^apply$/i }));
    expect(screen.getByRole("button", { name: /remove filter.*category.*beverages/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /remove filter.*product.*chai/i })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /clear all/i }));
    expect(screen.queryByRole("button", { name: /remove filter/i })).toBeNull();
  });

  test("the 'All' chip clears just that dimension", () => {
    renderBar(dashboard());
    fireEvent.click(screen.getByRole("button", { name: "Beverages" }));
    const group = screen.getByRole("group", { name: /category/i });
    fireEvent.click(within(group).getByRole("button", { name: /^all$/i }));
    expect(screen.queryByRole("button", { name: /remove filter/i })).toBeNull();
  });
});
