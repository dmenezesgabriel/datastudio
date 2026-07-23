import type { Spec } from "@json-render/react";
import { useEffect, useMemo } from "react";

import { type FilterDimension, type FilterOption, filterDimensions } from "../dashboardFilters";
import { formatValue } from "../format";
import { type CrossFilter, useCrossFilter } from "../hooks/useCrossFilter";
import { useStuckToTop } from "../hooks/useStuckToTop";
import { isActive, pruneFilters, sameValue } from "../crossFilter";
import { FilterMultiSelect } from "./FilterMultiSelect";

// A dimension with at most this many values shows every value inline as toggle chips (recognition
// — you see the whole set); more than this falls back to a searchable multi-select popover so the
// bar stays compact.
const SEGMENT_MAX = 8;

/**
 * The explicit, always-visible filter controls for a dashboard — the discoverable counterpart
 * to click-a-mark. Auto-derives the filterable dimensions from the spec and renders one control
 * per dimension (chips for few values, a dropdown for many), plus the active selections as
 * removable chips and a "Clear all". Both the controls here and clicking a mark drive the same
 * shared `/crossFilter` state, so they stay in sync.
 *
 * Renders nothing when the dashboard has no filterable dimensions (e.g. a text answer). Must be
 * inside the dashboard's `JSONUIProvider`.
 */
export function DashboardFilterBar({ spec }: { spec: Spec | null }) {
  const dimensions = useMemo(() => filterDimensions(spec), [spec]);
  const crossFilter = useCrossFilter();
  const { filters, replace } = crossFilter;
  // The bar is sticky; it only gains its elevation shadow + squared bottom corners once pinned,
  // so scrolling content reads as passing *under* a raised toolbar (not colliding with a flat one).
  const [stuck, sentinelRef] = useStuckToTop();
  // An edit re-derives the dimensions; reconcile the active selection to them so a column the
  // edit removed (or a value it no longer yields) can't linger as a dangling filter chip. The
  // active selection lives outside the spec state, so json-render's reconciliation never touches
  // it — this is where it gets pruned. A no-op (same ref) when every selection is still valid.
  useEffect(() => {
    const pruned = pruneFilters(filters, dimensions);
    if (pruned !== filters) replace(pruned);
  }, [dimensions, filters, replace]);
  if (dimensions.length === 0) return null;
  return (
    <>
      {/* Zero-height marker just above the sticky bar; useStuckToTop watches it cross the
          container's top edge to know when the bar is pinned. */}
      <div ref={sentinelRef} className="filter-bar__sentinel" aria-hidden="true" />
      <section className={`filter-bar${stuck ? " is-stuck" : ""}`} aria-label="Filters">
        <span className="filter-bar__title">Filters</span>
        {dimensions.map((dimension) => (
          <FilterControl key={dimension.field} dimension={dimension} crossFilter={crossFilter} />
        ))}
        <ActiveFilters dimensions={dimensions} crossFilter={crossFilter} />
      </section>
    </>
  );
}

/** One dimension's control: a chip group when its values are few, a search popover when many. */
function FilterControl({ dimension, crossFilter }: { dimension: FilterDimension; crossFilter: CrossFilter }) {
  const control =
    dimension.options.length <= SEGMENT_MAX ? (
      <FilterChipGroup dimension={dimension} crossFilter={crossFilter} />
    ) : (
      <FilterMultiSelect dimension={dimension} crossFilter={crossFilter} />
    );
  return (
    <div className="filter-group" role="group" aria-label={dimension.label}>
      <span className="filter-group__label">{dimension.label}</span>
      {control}
    </div>
  );
}

/** Every value as a toggle chip (several can be active at once), preceded by an "All" chip that
 *  clears the dimension. Multi-select: clicking more chips adds them; clicking an active one drops it. */
function FilterChipGroup({ dimension, crossFilter }: { dimension: FilterDimension; crossFilter: CrossFilter }) {
  const { field } = dimension;
  const noneSelected = crossFilter.valuesOf(field).length === 0;
  return (
    <div className="filter-chips">
      <FilterChip label="All" active={noneSelected} onClick={() => crossFilter.clearField(field)} />
      {dimension.options.map((option) => (
        <FilterChip
          key={option.display}
          label={option.display}
          active={isActive(crossFilter.filters, field, option.value)}
          onClick={() => crossFilter.toggle(field, option.value)}
        />
      ))}
    </div>
  );
}

/** A single toggle chip; `aria-pressed` carries its selected state (not colour alone). */
function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`filter-chip${active ? " is-active" : ""}`} aria-pressed={active} onClick={onClick}>
      {label}
    </button>
  );
}

/** The active selections as removable chips — one per (field, value) so each value drops on its
 *  own — plus "Clear all"; nothing when none are active. */
function ActiveFilters({ dimensions, crossFilter }: { dimensions: FilterDimension[]; crossFilter: CrossFilter }) {
  const pairs = Object.entries(crossFilter.filters).flatMap(([field, values]) =>
    values.map((value) => [field, value] as [string, unknown]),
  );
  if (pairs.length === 0) return null;
  return (
    <div className="filter-active">
      {pairs.map(([field, value]) => (
        <button
          key={`${field}:${displayFor(dimensions, field, value)}`}
          type="button"
          className="filter-active__chip"
          aria-label={`Remove filter: ${labelFor(dimensions, field)} equals ${displayFor(dimensions, field, value)}`}
          onClick={() => crossFilter.toggle(field, value)}
        >
          <span>
            {labelFor(dimensions, field)} = <strong>{displayFor(dimensions, field, value)}</strong>
          </span>
          <span className="filter-active__x" aria-hidden="true">
            ✕
          </span>
        </button>
      ))}
      <button type="button" className="filter-active__clear" onClick={crossFilter.clearAll}>
        Clear all
      </button>
    </div>
  );
}

function labelFor(dimensions: FilterDimension[], field: string): string {
  return dimensions.find((dimension) => dimension.field === field)?.label ?? field;
}

/** The display string of an active value, from its dimension's options (falls back to format). */
function displayFor(dimensions: FilterDimension[], field: string, value: unknown): string {
  const options: FilterOption[] = dimensions.find((dimension) => dimension.field === field)?.options ?? [];
  return options.find((option) => sameValue(option.value, value))?.display ?? formatValue(value);
}
