import { useEffect, useMemo, useRef, useState } from "react";

import { sameValue } from "../crossFilter";
import type { FilterDimension, FilterOption } from "../dashboardFilters";
import type { CrossFilter } from "../hooks/useCrossFilter";
import { usePopover } from "../hooks/usePopover";

/**
 * The multi-select control for a high-cardinality dimension: a disclosure button that summarises
 * the *applied* selection ("All" / a single value / "N selected") and opens a searchable checkbox
 * list. Unlike the inline chips, the popover **stages a draft** — ticking boxes builds up a pending
 * selection that only runs the filter when the user clicks **Apply**, so combining several values
 * refilters the widgets once, not on every tick. Escape / clicking away discards the draft. Native
 * checkboxes give keyboard + screen-reader support for free (no custom listbox).
 */
export function FilterMultiSelect({
  dimension,
  crossFilter,
}: {
  dimension: FilterDimension;
  crossFilter: CrossFilter;
}) {
  const { field, label, options } = dimension;
  const { open, toggleOpen, close, triggerRef, panelRef } = usePopover<HTMLButtonElement, HTMLDivElement>();
  const applied = crossFilter.valuesOf(field);
  const summary = summarize(applied, options);
  const apply = (values: unknown[]) => {
    crossFilter.setField(field, values);
    close();
    triggerRef.current?.focus(); // the panel is unmounting — don't strand focus on nothing
  };
  return (
    <div className="filter-multiselect">
      <button
        ref={triggerRef}
        type="button"
        className="filter-multiselect__trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        // The dimension label rides in the accessible name so the control is self-describing
        // (the visible group label sits beside it, but the name must stand alone for AT).
        aria-label={`${label}: ${summary}`}
        onClick={toggleOpen}
      >
        <span>{summary}</span>
        <span aria-hidden="true" className="filter-multiselect__caret">
          ▾
        </span>
      </button>
      {open && (
        // Fresh mount per open, so the draft always starts from the currently-applied selection.
        <FilterPopoverPanel panelRef={panelRef} label={label} options={options} applied={applied} onApply={apply} />
      )}
    </div>
  );
}

/**
 * The floating panel: a search box, a checkbox list bound to a local **draft**, and a footer whose
 * Apply commits the draft. The draft seeds from `applied` on mount (a fresh mount each open), so
 * dismissing without Apply leaves the running filter untouched.
 */
function FilterPopoverPanel({
  panelRef,
  label,
  options,
  applied,
  onApply,
}: {
  panelRef: React.RefObject<HTMLDivElement | null>;
  label: string;
  options: FilterOption[];
  applied: unknown[];
  onApply: (values: unknown[]) => void;
}) {
  const [draft, setDraft] = useState<unknown[]>(applied);
  const [query, setQuery] = useState("");
  const visible = useMemo(() => matchingOptions(options, query), [options, query]);
  const dirty = !sameValueSet(draft, applied);
  const toggleDraft = (value: unknown) =>
    setDraft((current) =>
      current.some((selected) => sameValue(selected, value))
        ? current.filter((selected) => !sameValue(selected, value))
        : [...current, value],
    );
  return (
    <div ref={panelRef} role="dialog" aria-label={`${label} filter`} className="filter-popover">
      <SearchBox label={label} query={query} onQuery={setQuery} />
      <DraftOptionList options={visible} draft={draft} onToggle={toggleDraft} />
      <div className="filter-popover__footer">
        <div className="filter-popover__staging">
          <button
            type="button"
            className="filter-popover__action"
            disabled={visible.length === 0}
            onClick={() => setDraft(unionValues(draft, visible))}
          >
            Select all
          </button>
          <button
            type="button"
            className="filter-popover__action"
            disabled={draft.length === 0}
            onClick={() => setDraft([])}
          >
            Clear
          </button>
        </div>
        <button type="button" className="filter-popover__apply" disabled={!dirty} onClick={() => onApply(draft)}>
          Apply
        </button>
      </div>
    </div>
  );
}

/** The search field; autofocused on open so a keyboard user lands in it, not on the first box. */
function SearchBox({ label, query, onQuery }: { label: string; query: string; onQuery: (value: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => inputRef.current?.focus(), []);
  return (
    <input
      ref={inputRef}
      type="search"
      className="filter-popover__search"
      aria-label={`Search ${label}`}
      placeholder={`Search ${label}…`}
      value={query}
      onChange={(event) => onQuery(event.target.value)}
    />
  );
}

/** The checkbox list bound to the draft; each row toggles one value. Muted note when none match. */
function DraftOptionList({
  options,
  draft,
  onToggle,
}: {
  options: FilterOption[];
  draft: unknown[];
  onToggle: (value: unknown) => void;
}) {
  if (options.length === 0) return <p className="filter-popover__empty">No matches</p>;
  return (
    <ul className="filter-popover__list">
      {options.map((option) => (
        <li key={option.display}>
          <label className="filter-popover__option">
            <input
              type="checkbox"
              checked={draft.some((value) => sameValue(value, option.value))}
              onChange={() => onToggle(option.value)}
            />
            <span>{option.display}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}

/** The trigger's label: "All" when none, the single value's display when one, else "N selected". */
function summarize(selected: unknown[], options: FilterOption[]): string {
  if (selected.length === 0) return "All";
  if (selected.length === 1) return displayOf(selected[0], options);
  return `${selected.length} selected`;
}

/** The options whose display contains `query` (case-insensitive); all of them when the query is empty. */
function matchingOptions(options: FilterOption[], query: string): FilterOption[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") return options;
  return options.filter((option) => option.display.toLowerCase().includes(needle));
}

/** The current draft plus every visible option not already in it (no duplicates). */
function unionValues(draft: unknown[], visible: FilterOption[]): unknown[] {
  const added = visible
    .map((option) => option.value)
    .filter((value) => !draft.some((current) => sameValue(current, value)));
  return [...draft, ...added];
}

/** Whether two value lists hold the same set (order-independent) — the draft's "dirty" test. */
function sameValueSet(a: unknown[], b: unknown[]): boolean {
  return a.length === b.length && a.every((value) => b.some((other) => sameValue(other, value)));
}

/** The display string for a raw value, from its dimension's options (falls back to String). */
function displayOf(value: unknown, options: FilterOption[]): string {
  return options.find((option) => sameValue(option.value, value))?.display ?? String(value);
}
