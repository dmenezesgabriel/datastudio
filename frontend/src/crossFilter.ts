/**
 * Client-side coordinated cross-filtering over a dashboard's already-loaded widget rows.
 *
 * The dashboard's active selection is a set of `{field: value}` entries — one value per
 * dimension, **AND-composed** (a row must match every active field it carries). It lives in
 * the shared json-render state at {@link FILTER_PATH}, so every widget in the same
 * `JSONUIProvider` sees it. A widget applies the filters to its OWN rows: siblings that carry
 * a selected column coordinate; those that don't are an untouched no-op (each widget is an
 * independent, pre-aggregated SQL result, so dimensions only overlap where a column matches).
 *
 * Pure module (no React): the `useCrossFilter` hook owns the state read/write, the registry
 * wrappers own the per-component semantics, and `DashboardFilterBar` drives it explicitly.
 */

/** A widget row as resolved from `/widget-N/rows`: a column-name → cell map. */
export type FilterableRow = Record<string, unknown>;

/** The dashboard's active selections: one raw value per filtered field. `{}` = nothing filtered. */
export type ActiveFilters = Record<string, unknown>;

/** Reserved state path the active filters are stored under (never collides with widget ids). */
export const FILTER_PATH = "/crossFilter";

/**
 * Whether two raw cell values are the same selection. Identity only — no coercion, so a
 * numeric label (`40`) and its string form (`"40"`) are distinct selections.
 */
export function sameValue(a: unknown, b: unknown): boolean {
  return Object.is(a, b);
}

/** Whether at least one row carries `field` as a column (else a filter on it is a no-op). */
export function rowsHaveField(rows: FilterableRow[], field: string): boolean {
  return rows.some((row) => field in row);
}

/** Whether `field` currently holds the selection `value`. */
export function isActive(filters: ActiveFilters, field: string, value: unknown): boolean {
  return field in filters && sameValue(filters[field], value);
}

/** The value selected for `field`, or `undefined` when it is not filtered. */
export function valueFor(filters: ActiveFilters, field: string): unknown {
  return filters[field];
}

/** How many fields are currently filtered. */
export function activeCount(filters: ActiveFilters): number {
  return Object.keys(filters).length;
}

/**
 * Whether `row` satisfies every active filter it carries (AND-composed). A filter on a field
 * the row lacks is ignored, so an unrelated widget stays a no-op. `excludeField` drops one
 * field from the predicate — used by a chart to keep (not filter) its own grouped dimension.
 */
export function matchesAllFilters(
  row: FilterableRow,
  filters: ActiveFilters,
  excludeField?: string,
): boolean {
  for (const field of Object.keys(filters)) {
    if (field === excludeField || !(field in row)) continue;
    if (!sameValue(row[field], filters[field])) return false;
  }
  return true;
}

/**
 * The rows a widget should render under the active filters. Returns the SAME array reference
 * (a no-op) when no active filter applies to these rows, so an unaffected widget never
 * re-renders on an unrelated selection.
 */
export function applyFilters(
  rows: FilterableRow[],
  filters: ActiveFilters,
  excludeField?: string,
): FilterableRow[] {
  const applies = Object.keys(filters).some(
    (field) => field !== excludeField && rowsHaveField(rows, field),
  );
  if (!applies) return rows;
  return rows.filter((row) => matchesAllFilters(row, filters, excludeField));
}

/**
 * The index of the first row matching the selection on `field`, for emphasising the source
 * mark (a chart whose `labelColumn` is filtered keeps all bars and highlights this one).
 * `null` when the field is not filtered or nothing matches.
 */
export function activeIndexFor(
  rows: FilterableRow[],
  field: string,
  filters: ActiveFilters,
): number | null {
  if (!(field in filters)) return null;
  const index = rows.findIndex((row) => field in row && sameValue(row[field], filters[field]));
  return index >= 0 ? index : null;
}
