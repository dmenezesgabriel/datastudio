import { afterEach, describe, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { WidgetFrame } from "./WidgetFrame";

afterEach(cleanup);

describe("WidgetFrame", () => {
  test("renders the widget with no toggle when there is no SQL", () => {
    const { container } = render(
      <WidgetFrame sql="">
        <div>chart</div>
      </WidgetFrame>,
    );
    expect(screen.getByText("chart")).toBeTruthy();
    expect(container.querySelector(".widget-frame__sql-toggle")).toBeNull();
    // No tool row either: a widget with no SQL reserves no space for a control it lacks.
    expect(container.querySelector(".widget-frame__tools")).toBeNull();
  });

  test("shows the widget by default and the SQL after toggling", () => {
    render(
      <WidgetFrame sql="SELECT 1">
        <div>chart</div>
      </WidgetFrame>,
    );
    // Preview is the default: the widget shows, the SQL does not
    expect(screen.getByText("chart")).toBeTruthy();
    expect(screen.queryByText("SELECT 1")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Show SQL" }));
    expect(screen.getByText("SELECT 1")).toBeTruthy();
    expect(screen.queryByText("chart")).toBeNull();
  });

  test("toggles back to the widget on a second click", () => {
    render(
      <WidgetFrame sql="SELECT 1">
        <div>chart</div>
      </WidgetFrame>,
    );
    const toggle = screen.getByRole("button", { name: "Show SQL" });
    fireEvent.click(toggle);
    fireEvent.click(toggle);
    expect(screen.getByText("chart")).toBeTruthy();
    expect(screen.queryByText("SELECT 1")).toBeNull();
  });

  test("carries state in aria-pressed, not in a swapped accessible name", () => {
    render(
      <WidgetFrame sql="SELECT 1">
        <div>chart</div>
      </WidgetFrame>,
    );
    const toggle = screen.getByRole("button", { name: "Show SQL" });
    expect(toggle.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-pressed")).toBe("true");
    // The name stays put: state lives in aria-pressed. Swapping the label too would
    // double-encode it, and a screen reader would announce the change twice.
    expect(screen.getByRole("button", { name: "Show SQL" })).toBe(toggle);
  });

  test("keeps the toggle outside the body, in its own row above it", () => {
    // The structural guarantee that replaced the absolute overlay: the control cannot
    // overlap widget content because it is never inside the box that holds it
    // (audit follow-up — the overlaid Preview/SQL pill sat on top of KPI figures).
    const { container } = render(
      <WidgetFrame sql="SELECT 1">
        <div>chart</div>
      </WidgetFrame>,
    );
    expect(container.querySelector(".widget-frame__body .widget-frame__sql-toggle")).toBeNull();
    const body = container.querySelector(".widget-frame__body");
    expect(body?.previousElementSibling?.className).toBe("widget-frame__tools");
  });

  test("exposes the SQL block as a focusable, labelled scroll region", () => {
    // A long query scrolls inside its own box rather than spilling over the neighbouring
    // grid cell, and a scrollable region with no keyboard access fails WCAG 2.1.1 — the
    // same treatment DataTable's .table-scroll already gets.
    render(
      <WidgetFrame sql="SELECT category, amount FROM events GROUP BY category">
        <div>chart</div>
      </WidgetFrame>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Show SQL" }));
    const sqlRegion = screen.getByRole("group", { name: "SQL query" });
    expect(sqlRegion.tabIndex).toBe(0);
    expect(sqlRegion.className).toBe("widget-frame__sql");
  });

  test("points the toggle at the body it swaps", () => {
    const { container } = render(
      <WidgetFrame sql="SELECT 1">
        <div>chart</div>
      </WidgetFrame>,
    );
    const toggle = screen.getByRole("button", { name: "Show SQL" });
    const body = container.querySelector(".widget-frame__body");
    expect(body?.id).toBeTruthy();
    expect(toggle.getAttribute("aria-controls")).toBe(body?.id);
  });
});
