import type { Spec } from "@json-render/react";

import { sameValue } from "./crossFilter";
import { formatLabel, isNumericColumn } from "./format";
import type { SpecWithState } from "./types";

/** One selectable value within a dimension: the raw value plus its display string. */
export interface FilterOption {
  value: unknown;
  display: string;
}

/** A dashboard dimension the user can filter on, with its distinct values. */
export interface FilterDimension {
  /** The column name filtered on (matches widget row keys). */
  field: string;
  /** A human-readable label for the control (`categoryName` → "Category Name"). */
  label: string;
  /** True when ≥2 widgets carry this column (so a selection coordinates them). */
  shared: boolean;
  /** Distinct values, sorted, each with a display string. */
  options: FilterOption[];
}

type WidgetState = { columns?: string[]; rows?: Record<string, unknown>[] };

/**
 * Turn a field name into a readable control label: split camelCase and snake_case, Title Case.
 *
 * @example humanizeField("categoryName") // "Category Name"
 */
export function humanizeField(field: string): string {
  return field
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Derive the dashboard's filterable dimensions from its spec + resolved state — the values the
 * `DashboardFilterBar` offers. A dimension is a **chart's `labelColumn`** (the axis it groups
 * by) or a **table's non-numeric column**; measures and a chart's other columns (e.g. a `bar`
 * sparkline) are excluded, and a column with fewer than two distinct values is dropped (nothing
 * to filter). Shared dimensions (carried by ≥2 widgets, where cross-filtering coordinates) come
 * first. Reads only the app's own `SpecWithState`, never framework internals.
 *
 * @example filterDimensions(spec) // [{ field: "categoryName", shared: true, options: [...] }, ...]
 */
export function filterDimensions(spec: Spec | null): FilterDimension[] {
  const state = (spec as SpecWithState | null)?.state ?? {};
  const byField = new Map<string, { widgets: Set<string>; values: unknown[] }>();
  for (const element of Object.values((spec?.elements ?? {}) as Record<string, RawElement>)) {
    for (const [field, rows] of dimensionsOf(element, state)) {
      const entry = byField.get(field) ?? { widgets: new Set<string>(), values: [] };
      entry.widgets.add(stateKeyOf(element) ?? field);
      for (const row of rows) if (field in row) entry.values.push(row[field]);
      byField.set(field, entry);
    }
  }
  return buildDimensions(byField);
}

type RawElement = { type?: string; props?: Record<string, unknown> };

/** The `(field, rows)` pairs one element contributes: a chart's labelColumn, a table's dims. */
function dimensionsOf(
  element: RawElement,
  state: Record<string, unknown>,
): [string, Record<string, unknown>[]][] {
  const key = stateKeyOf(element);
  const widget = (key ? state[key] : undefined) as WidgetState | undefined;
  const rows = widget?.rows ?? [];
  if (element.type === "ChartJs") {
    const label = element.props?.labelColumn;
    return typeof label === "string" ? [[label, rows]] : [];
  }
  if (element.type === "DataTable") {
    return (widget?.columns ?? [])
      .filter((column) => !isNumericColumn(rows, column))
      .map((column) => [column, rows] as [string, Record<string, unknown>[]]);
  }
  return [];
}

/** The state key an element's data binds to (`/w/rows` and `/w` → `w`). */
function stateKeyOf(element: RawElement): string | null {
  const data = element.props?.data as { $state?: string } | undefined;
  const path = data?.$state;
  if (typeof path !== "string") return null;
  return path.split("/").filter(Boolean)[0] ?? null;
}

/** Turn the accumulated fields into sorted, de-duplicated dimensions, shared-first. */
function buildDimensions(
  byField: Map<string, { widgets: Set<string>; values: unknown[] }>,
): FilterDimension[] {
  const dims: FilterDimension[] = [];
  for (const [field, { widgets, values }] of byField) {
    const options = distinctOptions(values);
    if (options.length < 2) continue; // nothing to choose between
    dims.push({ field, label: humanizeField(field), shared: widgets.size >= 2, options });
  }
  // Shared dimensions first (their selection coordinates widgets); stable otherwise.
  return dims.sort((a, b) => Number(b.shared) - Number(a.shared));
}

/** Distinct raw values (skipping empties), each with a display string, sorted for display. */
function distinctOptions(values: unknown[]): FilterOption[] {
  const seen: unknown[] = [];
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    if (!seen.some((kept) => sameValue(kept, value))) seen.push(value);
  }
  return seen
    .map((value) => ({ value, display: formatLabel(value) }))
    .sort((a, b) => a.display.localeCompare(b.display, undefined, { numeric: true }));
}
