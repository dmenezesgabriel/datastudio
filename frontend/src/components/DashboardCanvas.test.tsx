import type { Spec } from "@json-render/react";
import { afterEach, describe, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import { DashboardCanvas } from "./DashboardCanvas";
import type { SpecWithState } from "../types";

afterEach(cleanup);

// A dashboard of one detail table whose category column is a filterable dimension.
function tableDashboard(): SpecWithState {
  return {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["t"] },
      t: { type: "DataTable", props: { data: { $state: "/d" } }, children: [] },
    },
    state: { d: { columns: ["category"], rows: [{ category: "Books" }, { category: "Toys" }] } },
  };
}

// The category filter group in a given dashboard container.
function categoryGroup() {
  return within(screen.getByRole("group", { name: /category/i }));
}

describe("DashboardCanvas", () => {
  test("renders the spec's widgets and the explicit filter bar", () => {
    render(<DashboardCanvas spec={tableDashboard() as Spec} loading={false} />);
    // The widget itself (the table) and the derived filter control both render.
    expect(within(screen.getByRole("group", { name: /data table/i })).getAllByRole("button").length).toBeGreaterThan(0);
    expect(screen.getByText("Filters")).toBeTruthy();
  });

  test("surfaces an active-filter chip once a dimension is selected in the bar", () => {
    render(<DashboardCanvas spec={tableDashboard() as Spec} loading={false} />);
    expect(screen.queryByRole("button", { name: /remove filter/i })).toBeNull();
    fireEvent.click(categoryGroup().getByRole("button", { name: "Books" }));
    expect(screen.getByRole("button", { name: /remove filter.*category.*books/i })).toBeTruthy();
  });

  test("scopes the filter to its own provider: a second dashboard is independent", () => {
    render(
      <>
        <DashboardCanvas spec={tableDashboard() as Spec} loading={false} />
        <DashboardCanvas spec={tableDashboard() as Spec} loading={false} />
      </>,
    );
    // Select in the first dashboard's filter bar only.
    fireEvent.click(within(screen.getAllByRole("group", { name: /category/i })[0]).getByRole("button", { name: "Books" }));
    expect(screen.getAllByRole("button", { name: /remove filter/i }).length).toBe(1);
  });
});
