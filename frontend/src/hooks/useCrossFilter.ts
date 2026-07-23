import { useCallback } from "react";
import { useStateStore, useStateValue } from "@json-render/react";

import {
  type ActiveFilters,
  activeCount as countActive,
  FILTER_PATH,
  isActive,
  valueFor,
} from "../crossFilter";

// A stable empty reference so an unfiltered dashboard doesn't hand out a new object each render.
const NONE: ActiveFilters = {};

/** What a widget or control needs to read and drive the dashboard's shared cross-filters. */
export interface CrossFilter {
  /** The active selections (`{field: value}`), AND-composed. `{}` when nothing is filtered. */
  filters: ActiveFilters;
  /** Number of fields currently filtered. */
  activeCount: number;
  /** Set `field = value` (replacing any prior value for that field). */
  select: (field: string, value: unknown) => void;
  /** Set `field = value`, or clear the field when that exact value is already active. */
  toggle: (field: string, value: unknown) => void;
  /** Replace the whole selection set at once (used to reconcile after a spec edit). */
  replace: (next: ActiveFilters) => void;
  /** Clear one field's selection. */
  clearField: (field: string) => void;
  /** Clear every selection. */
  clearAll: () => void;
  /** The value selected for `field`, or `undefined`. */
  valueOf: (field: string) => unknown;
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

  const select = useCallback(
    (field: string, value: unknown) => set(FILTER_PATH, { ...filters, [field]: value }),
    [filters, set],
  );
  const clearField = useCallback(
    (field: string) => {
      const next = { ...filters };
      delete next[field];
      set(FILTER_PATH, next);
    },
    [filters, set],
  );
  const toggle = useCallback(
    (field: string, value: unknown) =>
      isActive(filters, field, value) ? clearField(field) : select(field, value),
    [filters, select, clearField],
  );
  const replace = useCallback((next: ActiveFilters) => set(FILTER_PATH, next), [set]);
  const clearAll = useCallback(() => set(FILTER_PATH, {}), [set]);
  const valueOf = useCallback((field: string) => valueFor(filters, field), [filters]);

  return { filters, activeCount: countActive(filters), select, toggle, replace, clearField, clearAll, valueOf };
}
