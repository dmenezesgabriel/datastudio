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

  // An edit swaps the spec under the same provider (ArtifactView re-fetches on onComplete). The
  // /crossFilter selection lives outside the spec state, so it survives that swap — these pin
  // that the bar reconciles it to the edited dimensions instead of leaving a dangling chip.
  test("an edit that drops a dimension prunes its now-orphaned active filter", () => {
    const { rerender } = render(<DashboardCanvas spec={twoDimDashboard() as Spec} loading={false} />);
    fireEvent.click(categoryGroup().getByRole("button", { name: "Books" }));
    expect(screen.getByRole("button", { name: /remove filter.*category.*books/i })).toBeTruthy();
    // The edited spec keeps only the region column — category is no longer a dimension.
    rerender(<DashboardCanvas spec={regionOnlyDashboard() as Spec} loading={false} />);
    expect(screen.queryByRole("button", { name: /remove filter.*category/i })).toBeNull();
  });

  test("an edit keeps an active filter whose dimension and value survive", () => {
    const { rerender } = render(<DashboardCanvas spec={twoDimDashboard() as Spec} loading={false} />);
    fireEvent.click(within(screen.getByRole("group", { name: /region/i })).getByRole("button", { name: "West" }));
    rerender(<DashboardCanvas spec={regionOnlyDashboard() as Spec} loading={false} />);
    // Region still exists with "West" among its values, so the selection stays applied.
    expect(screen.getByRole("button", { name: /remove filter.*region.*west/i })).toBeTruthy();
  });
});

// A table with two filterable dimensions (category, region) sharing the rows below.
function twoDimDashboard(): SpecWithState {
  return {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["t"] },
      t: { type: "DataTable", props: { data: { $state: "/d" } }, children: [] },
    },
    state: {
      d: {
        columns: ["category", "region"],
        rows: [{ category: "Books", region: "West" }, { category: "Toys", region: "East" }],
      },
    },
  };
}

// The same dashboard after an edit that drops the category column: only region remains.
function regionOnlyDashboard(): SpecWithState {
  return {
    root: "root",
    elements: {
      root: { type: "Stack", props: {}, children: ["t"] },
      t: { type: "DataTable", props: { data: { $state: "/d" } }, children: [] },
    },
    state: { d: { columns: ["region"], rows: [{ region: "West" }, { region: "East" }] } },
  };
}
