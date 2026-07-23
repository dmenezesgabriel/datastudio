import { useCallback } from "react";
import { useStateStore, useStateValue } from "@json-render/react";

import {
  type ActiveFilters,
  activeCount as countActive,
  FILTER_PATH,
  isActive,
  sameValue,
  valuesFor,
  withField,
} from "../crossFilter";

// A stable empty reference so an unfiltered dashboard doesn't hand out a new object each render.
const NONE: ActiveFilters = {};

/** What a widget or control needs to read and drive the dashboard's shared cross-filters. */
export interface CrossFilter {
  /** The active selections (`{field: [value, ...]}`), OR-within a field, AND-across fields. */
  filters: ActiveFilters;
  /** Number of fields currently filtered (not values). */
  activeCount: number;
  /** Add `value` to `field`'s set, or remove it when that exact value is already selected. */
  toggle: (field: string, value: unknown) => void;
  /** Replace `field`'s whole value set (used by the popover's "Select all" / "Clear"). */
  setField: (field: string, values: unknown[]) => void;
  /** Replace the whole selection set at once (used to reconcile after a spec edit). */
  replace: (next: ActiveFilters) => void;
  /** Clear one field's selection. */
  clearField: (field: string) => void;
  /** Clear every selection. */
  clearAll: () => void;
  /** The values selected for `field` (a stable empty array when none). */
  valuesOf: (field: string) => unknown[];
}

/**
 * Read and drive the dashboard's cross-filters, stored in the shared json-render state at
 * {@link FILTER_PATH}. Reads subscribe (a widget re-renders when the selection changes) via
 * `useStateValue`; writes go through the store's `set` — json-render's designed two-way state
 * API — so a click in one widget, or a pick in the filter bar, coordinates every sibling.
 *
 * A new object reference is written on every change (json-render compares state by reference).
 * Must be called inside a `JSONUIProvider` (the per-dashboard store).
 */
export function useCrossFilter(): CrossFilter {
  const filters = useStateValue<ActiveFilters>(FILTER_PATH) ?? NONE;
  const { set } = useStateStore();

  const toggle = useCallback(
    (field: string, value: unknown) => {
      const current = valuesFor(filters, field);
      const next = isActive(filters, field, value)
        ? current.filter((selected) => !sameValue(selected, value))
        : [...current, value];
      set(FILTER_PATH, withField(filters, field, next));
    },
    [filters, set],
  );
  const setField = useCallback(
    (field: string, values: unknown[]) => set(FILTER_PATH, withField(filters, field, values)),
    [filters, set],
  );
  const clearField = useCallback(
    (field: string) => set(FILTER_PATH, withField(filters, field, [])),
    [filters, set],
  );
  const replace = useCallback((next: ActiveFilters) => set(FILTER_PATH, next), [set]);
  const clearAll = useCallback(() => set(FILTER_PATH, {}), [set]);
  const valuesOf = useCallback((field: string) => valuesFor(filters, field), [filters]);

  return { filters, activeCount: countActive(filters), toggle, setField, replace, clearField, clearAll, valuesOf };
}
