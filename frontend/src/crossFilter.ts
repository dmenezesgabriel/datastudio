/**
 * Client-side coordinated cross-filtering over a dashboard's already-loaded widget rows.
 *
 * The dashboard's active selection is a set of `{field: [value, ...]}` entries — a **set of
 * values per dimension**, composed as `field IN (values)` **OR-within a field, AND-across
 * fields** (a row must match every filtered field it carries, by being one of that field's
 * selected values). It lives in the shared json-render state at {@link FILTER_PATH}, so every
 * widget in the same `JSONUIProvider` sees it. A widget applies the filters to its OWN rows:
 * siblings that carry a selected column coordinate; those that don't are an untouched no-op
 * (each widget is an independent, pre-aggregated SQL result, so dimensions only overlap where a
 * column matches). Single-select is the degenerate case — a set of size one.
 *
 * Pure module (no React): the `useCrossFilter` hook owns the state read/write, the registry
 * wrappers own the per-component semantics, and `DashboardFilterBar` drives it explicitly.
 */

/** A widget row as resolved from `/widget-N/rows`: a column-name → cell map. */
export type FilterableRow = Record<string, unknown>;

/**
 * The dashboard's active selections: a set of raw values per filtered field. A field key is
 * present **iff** it has ≥1 selected value (every mutator upholds this — see {@link withField}).
 * `{}` = nothing filtered.
 */
export type ActiveFilters = Record<string, unknown[]>;

/** Reserved state path the active filters are stored under (never collides with widget ids). */
export const FILTER_PATH = "/crossFilter";

// A stable empty reference so an unfiltered field doesn't hand out a new array each read.
const NO_VALUES: readonly unknown[] = [];

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

/** Whether `value` is one of the currently selected values for `field`. */
export function isActive(filters: ActiveFilters, field: string, value: unknown): boolean {
  return (filters[field] ?? NO_VALUES).some((selected) => sameValue(selected, value));
}

/** The set of values selected for `field`, or a stable empty array when it is not filtered. */
export function valuesFor(filters: ActiveFilters, field: string): unknown[] {
  return filters[field] ?? (NO_VALUES as unknown[]);
}

/** How many fields are currently filtered (not how many values). */
export function activeCount(filters: ActiveFilters): number {
  return Object.keys(filters).length;
}

/**
 * Return a copy of `filters` with `field` set to `values` — or with the key **omitted** when
 * `values` is empty, upholding the "present iff non-empty" invariant. The single home for the
 * per-field set mutation, so every hook mutator (toggle/setField/clearField) shares one rule and
 * never leaves an empty-array key behind. Never mutates the input.
 *
 * @example withField({ region: ["West"] }, "category", ["Books"]) // { region: ["West"], category: ["Books"] }
 * @example withField({ category: ["Books"] }, "category", []) // {} — the empty key is dropped
 */
export function withField(filters: ActiveFilters, field: string, values: unknown[]): ActiveFilters {
  const next = { ...filters };
  if (values.length === 0) delete next[field];
  else next[field] = values;
  return next;
}

/**
 * Whether `row` satisfies every active filter it carries: for each filtered field the row has,
 * its cell must be one of that field's selected values (OR within the field), and every such
 * field must pass (AND across fields). A filter on a field the row lacks is ignored, so an
 * unrelated widget stays a no-op. `excludeField` drops one field from the predicate — used by a
 * chart to keep (not filter) its own grouped dimension.
 */
export function matchesAllFilters(
  row: FilterableRow,
  filters: ActiveFilters,
  excludeField?: string,
): boolean {
  for (const field of Object.keys(filters)) {
    if (field === excludeField || !(field in row)) continue;
    if (!isActive(filters, field, row[field])) return false;
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
 * The dimension shape {@link pruneFilters} needs: a field and the raw values still selectable
 * on it. `FilterDimension` (dashboardFilters.ts) is structurally one of these — kept minimal
 * here so this module stays dependency-free (dashboardFilters imports from it, not the reverse).
 */
export interface SelectableDimension {
  field: string;
  options: { value: unknown }[];
}

/**
 * Drop selections that no longer correspond to a live dimension/value, at the **value** level.
 * Run after an edit re-derives the dashboard's dimensions: a column the edit removed, or a value
 * it no longer yields, would otherwise linger as a dangling active filter that filters nothing and
 * has no control to toggle it off. Each field keeps only its still-selectable values, and a field
 * with none surviving is dropped. Returns the SAME reference when every selection is still valid
 * (so the caller writes nothing and no re-render churns); otherwise a new object.
 *
 * @example pruneFilters({ category: ["Books", "Toys"] }, [{ field: "category", options: [{ value: "Toys" }] }])
 * // { category: ["Toys"] } — "Books" is gone, "Toys" survives
 */
export function pruneFilters(
  filters: ActiveFilters,
  dimensions: SelectableDimension[],
): ActiveFilters {
  const optionsByField = new Map(dimensions.map((dimension) => [dimension.field, dimension.options]));
  const kept: ActiveFilters = {};
  let changed = false;
  for (const [field, values] of Object.entries(filters)) {
    const options = optionsByField.get(field) ?? [];
    const survivors = values.filter((value) => options.some((option) => sameValue(option.value, value)));
    if (survivors.length > 0) kept[field] = survivors;
    if (survivors.length !== values.length) changed = true;
  }
  return changed ? kept : filters;
}

/**
 * The set of row indices whose `field` value is currently selected, for emphasising the source
 * marks (a chart whose `labelColumn` is filtered keeps all bars and highlights the selected ones).
 * Empty when the field is not filtered or nothing matches.
 */
export function activeIndicesFor(
  rows: FilterableRow[],
  field: string,
  filters: ActiveFilters,
): Set<number> {
  const active = new Set<number>();
  if (!(field in filters)) return active;
  rows.forEach((row, index) => {
    if (field in row && isActive(filters, field, row[field])) active.add(index);
  });
  return active;
}
