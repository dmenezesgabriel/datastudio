import { afterEach, describe, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { usePopover } from "./usePopover";

afterEach(cleanup);

// A minimal disclosure that wires the hook to a real trigger + panel, so the document-level
// dismiss behaviours run against actual DOM nodes (Escape focus return needs a live trigger).
function Disclosure() {
  const { open, toggleOpen, triggerRef, panelRef } = usePopover<HTMLButtonElement, HTMLDivElement>();
  return (
    <div>
      <button ref={triggerRef} aria-expanded={open} onClick={toggleOpen}>
        Toggle
      </button>
      {open && (
        <div ref={panelRef} role="dialog" aria-label="Panel">
          <button>Inside</button>
        </div>
      )}
      <button>Outside</button>
    </div>
  );
}

describe("usePopover", () => {
  test("the trigger toggles the panel open and closed", () => {
    render(<Disclosure />);
    const trigger = screen.getByRole("button", { name: "Toggle" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.click(trigger);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  test("Escape closes the panel and returns focus to the trigger", () => {
    render(<Disclosure />);
    const trigger = screen.getByRole("button", { name: "Toggle" });
    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  test("a pointerdown outside the trigger and panel closes it", () => {
    render(<Disclosure />);
    fireEvent.click(screen.getByRole("button", { name: "Toggle" }));
    fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  test("a pointerdown inside the panel keeps it open", () => {
    render(<Disclosure />);
    fireEvent.click(screen.getByRole("button", { name: "Toggle" }));
    fireEvent.pointerDown(screen.getByRole("button", { name: "Inside" }));
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
});
