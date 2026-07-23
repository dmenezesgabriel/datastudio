import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { MentionMenu } from "./MentionMenu";

afterEach(cleanup);

test("labels the listbox so assistive tech announces what it lists", () => {
  render(
    <MentionMenu
      id="m"
      label="Columns of olist_orders"
      hint="Enter to add column"
      matches={["order_id"]}
      highlighted={0}
      onPick={vi.fn()}
    />,
  );

  expect(screen.getByRole("listbox", { name: "Columns of olist_orders" })).toBeTruthy();
});

test("shows the drill affordance on each table row when a drill is offered", () => {
  render(
    <MentionMenu
      id="m"
      label="Tables"
      hint="Enter to add · . for columns"
      matches={["olist_orders", "olist_products"]}
      highlighted={0}
      onPick={vi.fn()}
      onDrill={vi.fn()}
    />,
  );

  expect(screen.getByRole("button", { name: "Show columns of olist_orders" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Show columns of olist_products" })).toBeTruthy();
});

test("the drill button opens the row's columns without picking the table", () => {
  const onPick = vi.fn();
  const onDrill = vi.fn();
  render(
    <MentionMenu
      id="m"
      label="Tables"
      hint="Enter to add · . for columns"
      matches={["olist_orders"]}
      highlighted={0}
      onPick={onPick}
      onDrill={onDrill}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Show columns of olist_orders" }));

  expect(onDrill).toHaveBeenCalledWith("olist_orders");
  expect(onPick).not.toHaveBeenCalled(); // the chevron drills; it does not commit the table
});

test("offers no drill affordance when drilling is not available (the column menu)", () => {
  render(
    <MentionMenu
      id="m"
      label="Columns of olist_orders"
      hint="Enter to add column"
      matches={["order_id"]}
      highlighted={0}
      onPick={vi.fn()}
    />,
  );

  expect(screen.queryByRole("button")).toBeNull();
});

test("shows the hint that tells the user how to reach columns", () => {
  render(
    <MentionMenu
      id="m"
      label="Tables"
      hint="Enter to add · . for columns"
      matches={["olist_orders"]}
      highlighted={0}
      onPick={vi.fn()}
      onDrill={vi.fn()}
    />,
  );

  expect(screen.getByText("Enter to add · . for columns")).toBeTruthy();
});

test("picking a row still commits it", () => {
  const onPick = vi.fn();
  render(
    <MentionMenu
      id="m"
      label="Tables"
      hint="Enter to add · . for columns"
      matches={["olist_orders"]}
      highlighted={0}
      onPick={onPick}
      onDrill={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("option"));

  expect(onPick).toHaveBeenCalledWith("olist_orders");
});
