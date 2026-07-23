import { useCallback, useEffect, useRef, useState } from "react";

/** The open state plus the refs and controls a disclosure popover wires to its trigger + panel. */
export interface Popover<T extends HTMLElement, P extends HTMLElement> {
  open: boolean;
  /** Flip the panel open/closed (wire to the trigger's onClick). */
  toggleOpen: () => void;
  /** Close the panel (e.g. after a terminal action inside it). */
  close: () => void;
  /** Attach to the trigger button — Escape restores focus here, and clicks on it don't dismiss. */
  triggerRef: React.RefObject<T | null>;
  /** Attach to the panel element — clicks inside it don't dismiss. */
  panelRef: React.RefObject<P | null>;
}

/**
 * A dismissable disclosure popover: open state plus the two behaviours a floating panel needs to
 * feel native — **Escape** closes it and returns focus to the trigger (so keyboard focus is never
 * stranded on a hidden panel), and a **pointerdown outside** the trigger and panel closes it. The
 * document listeners attach only while open, so a closed popover costs nothing.
 *
 * Generic over the trigger and panel element types so the refs stay precisely typed at the call
 * site (`usePopover<HTMLButtonElement, HTMLDivElement>()`).
 *
 * @example
 *   const { open, toggleOpen, triggerRef, panelRef } = usePopover<HTMLButtonElement, HTMLDivElement>();
 *   <button ref={triggerRef} aria-expanded={open} onClick={toggleOpen}>Filter</button>
 *   {open && <div ref={panelRef} role="dialog">…</div>}
 */
export function usePopover<
  T extends HTMLElement = HTMLElement,
  P extends HTMLElement = HTMLElement,
>(): Popover<T, P> {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<T>(null);
  const panelRef = useRef<P>(null);

  const close = useCallback(() => setOpen(false), []);
  const toggleOpen = useCallback(() => setOpen((wasOpen) => !wasOpen), []);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus(); // don't strand focus on the vanished panel
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  return { open, toggleOpen, close, triggerRef, panelRef };
}
