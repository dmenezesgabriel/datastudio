import { Children, type ReactNode, useMemo } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";

import { type ActiveFilters, isActive } from "../crossFilter";

/** Vertical container for the rendered view elements. */
export function Stack({ children }: { children?: ReactNode }) {
  return <div className="flex flex-col gap-4">{children}</div>;
}

/** A band of KPI tiles laid across the top of a dashboard (the F-layout headline row).
 *  Renders nothing when empty so a single-widget or text answer shows no stray band. */
export function KpiRow({ children }: { children?: ReactNode }) {
  if (Children.count(children) === 0) return null;
  return <div className="kpi-row">{children}</div>;
}

/** A responsive grid region for a dashboard's charts and detail tables.
 *  Renders nothing when empty (see KpiRow). */
export function Grid({ children }: { children?: ReactNode }) {
  if (Children.count(children) === 0) return null;
  return <div className="dash-grid">{children}</div>;
}

/** The natural-language answer, rendered as sanitized markdown (headings, bold, lists). */
export function Markdown({ text }: { text: string }) {
  // Parsing + sanitizing is pure in `text`; memo so unrelated re-renders don't repeat it.
  const html = useMemo(
    () => DOMPurify.sanitize(marked.parse(text, { async: false })),
    [text],
  );
  return (
    <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

/** Direction of a KPI's change vs. its comparison value; drives the arrow + status color. */
export type DeltaDirection = "up" | "down" | "flat";

/** A KPI's period-over-period change: an already-formatted figure plus its direction. */
export interface KpiDelta {
  text: string;
  direction: DeltaDirection;
}

const DELTA_GLYPH: Record<DeltaDirection, string> = { up: "▲", down: "▼", flat: "→" };
const DELTA_ARIA: Record<DeltaDirection, string> = { up: "up", down: "down", flat: "no change" };

/** The change indicator: an arrow glyph + figure, so direction reads without relying on color. */
function KpiDeltaBadge({ text, direction }: KpiDelta) {
  return (
    <div className={`kpi-stat__delta kpi-stat__delta--${direction}`}>
      <span aria-hidden="true">{DELTA_GLYPH[direction]}</span>{" "}
      <span className="sr-only">{DELTA_ARIA[direction]} </span>
      {text}
    </div>
  );
}

/** A single headline metric with its caption and an optional period-over-period delta. */
export function KpiStat({
  label,
  value,
  delta,
}: {
  label: string;
  value: string;
  delta?: KpiDelta;
}) {
  return (
    <div className="kpi-stat border rounded-sm px-4 py-3">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-sm text-muted">{label}</div>
      {delta ? <KpiDeltaBadge {...delta} /> : null}
    </div>
  );
}

/** The raw result rows rendered as a plain table.
 *  `numericColumns[i]` right-aligns column i (measures align on the decimal; text
 *  columns stay left) — a Tufte table reads down a column of numbers by their tails.
 *
 *  When `onSelectCell` is given, cells in a non-numeric (dimension) column become
 *  keyboard-operable toggle buttons that drive the dashboard cross-filters: they emit the
 *  column and the RAW value from `rawRows` (the filter compares unformatted values). A cell
 *  whose column is in `activeValues` at its own value carries `aria-pressed` (several columns
 *  can be pressed at once, one per active filter). Measures stay plain — filtering by a number
 *  is meaningless. With no handler the table is read-only (e.g. an old-version preview). */
export function DataTable({
  columns,
  rows,
  numericColumns,
  rawRows,
  onSelectCell,
  activeValues,
}: {
  columns: string[];
  rows: unknown[][];
  numericColumns: boolean[];
  rawRows?: unknown[][];
  onSelectCell?: (column: string, value: unknown) => void;
  activeValues?: ActiveFilters;
}) {
  // A wide table scrolls inside this box rather than widening the page (CLAUDE.md).
  // The box is a focusable, labelled region so a keyboard user can reach it and scroll it
  // with the arrow keys — a scrollable region with no keyboard access fails WCAG 2.1.1
  // (a11y audit, exhaustive-check finding).
  return (
    <div className="table-scroll" tabIndex={0} role="group" aria-label="Data table">
      <table className="data-table text-base">
        <thead>
          <tr>
            {columns.map((column, columnIndex) => (
              <th key={column} className={numericColumns[columnIndex] ? "data-table__num" : undefined}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((value, columnIndex) => (
                <td key={columnIndex} className={numericColumns[columnIndex] ? "data-table__num" : undefined}>
                  <DataCell
                    display={String(value)}
                    column={columns[columnIndex]}
                    rawValue={rawRows?.[rowIndex]?.[columnIndex]}
                    selectable={!!onSelectCell && !numericColumns[columnIndex]}
                    active={
                      !!activeValues &&
                      isActive(activeValues, columns[columnIndex], rawRows?.[rowIndex]?.[columnIndex])
                    }
                    onSelect={onSelectCell}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One table cell: plain text, or a toggle button when its column drives the cross-filter. */
function DataCell({
  display,
  column,
  rawValue,
  selectable,
  active,
  onSelect,
}: {
  display: string;
  column: string;
  rawValue: unknown;
  selectable: boolean;
  active: boolean;
  onSelect?: (column: string, value: unknown) => void;
}) {
  if (!selectable || !onSelect) return <>{display}</>;
  return (
    <button
      type="button"
      className="data-table__select"
      aria-pressed={active}
      onClick={() => onSelect(column, rawValue)}
    >
      {display}
    </button>
  );
}
