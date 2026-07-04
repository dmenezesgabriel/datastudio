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
    expect(container.querySelector(".widget-frame__toggle")).toBeNull();
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

    fireEvent.click(screen.getByRole("button", { name: "SQL" }));
    expect(screen.getByText("SELECT 1")).toBeTruthy();
    expect(screen.queryByText("chart")).toBeNull();
  });

  test("marks the active mode via aria-pressed (not color alone)", () => {
    render(
      <WidgetFrame sql="SELECT 1">
        <div>chart</div>
      </WidgetFrame>,
    );
    const preview = screen.getByRole("button", { name: "Preview" });
    const sql = screen.getByRole("button", { name: "SQL" });
    expect(preview.getAttribute("aria-pressed")).toBe("true");
    expect(sql.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(sql);
    expect(preview.getAttribute("aria-pressed")).toBe("false");
    expect(sql.getAttribute("aria-pressed")).toBe("true");
  });
});
