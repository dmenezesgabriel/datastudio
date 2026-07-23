import type { Spec } from "@json-render/react";
import { JSONUIProvider } from "@json-render/react";
import { afterEach, describe, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import { DashboardFilterBar } from "./DashboardFilterBar";
import { registry } from "../registry";
import type { SpecWithState } from "../types";

afterEach(cleanup);

// Category (2 values → chip group, shared by chart+table) and Product (9 values → dropdown).
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

  test("shows a chip group for a low-cardinality dimension and a dropdown for a high-cardinality one", () => {
    renderBar(dashboard());
    expect(screen.getByRole("button", { name: "Beverages" })).toBeTruthy(); // category → chips
    expect(screen.getByRole("combobox", { name: /product/i })).toBeTruthy(); // product → dropdown
  });

  test("selecting a chip activates that filter (aria-pressed) and shows a removable active chip", () => {
    renderBar(dashboard());
    fireEvent.click(screen.getByRole("button", { name: "Beverages" }));
    expect(screen.getByRole("button", { name: "Beverages" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /remove filter.*category.*beverages/i })).toBeTruthy();
  });

  test("two dimensions compose (AND): both stay active, and Clear all resets them", () => {
    renderBar(dashboard());
    fireEvent.click(screen.getByRole("button", { name: "Beverages" }));
    fireEvent.change(screen.getByRole("combobox", { name: /product/i }), { target: { value: "Chai" } });
    // Both selections are shown as active chips.
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
