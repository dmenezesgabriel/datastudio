import { defineRegistry } from "@json-render/react";

import { catalog } from "./catalog";
import { activeIndexFor, applyFilters } from "./crossFilter";
import { useCrossFilter } from "./hooks/useCrossFilter";
import { ChartJsView, type ChartDataset } from "./components/ChartJsView";
import {
  DataTable,
  Grid,
  KpiRow,
  KpiStat,
  type KpiDelta,
  Markdown,
  Stack,
} from "./components/Panels";
import { WidgetEmptyState } from "./components/WidgetEmptyState";
import { WidgetFrame } from "./components/WidgetFrame";
import { formatCell, formatLabel, formatValue, isNumericColumn } from "./format";

// Bind each catalogue component to its React implementation. Data props arrive
// already resolved from provider state (the $state binding), as an array of row
// objects (`/result/rows`) or the `{columns, rows}` object (`/result`); these
// renderers shape that into the props each presentational component expects.
type Row = Record<string, unknown>;

function asRows(data: unknown): Row[] {
  return Array.isArray(data) ? (data as Row[]) : [];
}

function chartDatasets(rows: Row[], valueColumns: string[]): ChartDataset[] {
  return valueColumns.map((column) => ({
    label: column,
    data: rows.map((row) => toChartNumber(row[column])),
  }));
}

// A chart point is a finite number or a gap. A missing/empty cell or a non-numeric value
// becomes null (Chart.js renders it as a break in the series) rather than a spurious 0/NaN.
function toChartNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

// Build the KPI's trend badge from a signed change column. Direction comes from the
// sign (arrow + status color reinforce each other); a non-numeric cell yields no badge.
function deltaFrom(row: Row, deltaColumn?: string, deltaLabel?: string): KpiDelta | undefined {
  if (!deltaColumn) return undefined;
  const raw = Number(row[deltaColumn]);
  if (!Number.isFinite(raw)) return undefined;
  const direction = raw > 0 ? "up" : raw < 0 ? "down" : "flat";
  const sign = raw > 0 ? "+" : "";
  const suffix = deltaLabel ? ` ${deltaLabel}` : "";
  return { direction, text: `${sign}${formatValue(raw)}${suffix}` };
}

export const { registry } = defineRegistry(catalog, {
  components: {
    Stack: ({ children }) => <Stack>{children}</Stack>,
    KpiRow: ({ children }) => <KpiRow>{children}</KpiRow>,
    Grid: ({ children }) => <Grid>{children}</Grid>,
    // Backend-owned wrapper: receives both the widget's SQL (prop) and its rendered
    // visualization (children) — see BaseComponentProps in @json-render/react.
    WidgetFrame: ({ props, children }) => <WidgetFrame sql={props.sql}>{children}</WidgetFrame>,
    Markdown: ({ props }) => <Markdown text={props.text} />,
    // The KPI recomputes over the filtered rows, so a headline number tracks the active
    // selections when its result carries those columns (otherwise applyFilters is a no-op).
    KpiStat: ({ props }) => {
      const { filters } = useCrossFilter();
      const rows = applyFilters(asRows(props.data), filters);
      const row = rows[0];
      const value = row ? formatValue(row[props.valueColumn]) : "";
      const delta = row ? deltaFrom(row, props.deltaColumn, props.deltaLabel) : undefined;
      return <KpiStat label={props.label} value={value} delta={delta} />;
    },
    // A chart is both a filter source (clicking a mark selects its labelColumn value) and a
    // target. It filters its rows by every OTHER active dimension, but keeps its OWN grouped
    // dimension (labelColumn) and emphasises the selected mark instead of dropping bars.
    // Selections carry the RAW label value so the filter compares unformatted.
    ChartJs: ({ props }) => {
      const { filters, toggle } = useCrossFilter();
      const allRows = asRows(props.data);
      const rows = applyFilters(allRows, filters, props.labelColumn);
      const activeIndex = activeIndexFor(allRows, props.labelColumn, filters);
      if (rows.length === 0) return <WidgetEmptyState />;
      return (
        <ChartJsView
          kind={props.kind}
          title={props.title}
          labels={rows.map((row) => formatLabel(row[props.labelColumn]))}
          datasets={chartDatasets(rows, props.valueColumns)}
          activeIndex={activeIndex}
          onSelect={(index) => toggle(props.labelColumn, rows[index][props.labelColumn])}
        />
      );
    },
    DataTable: ({ props }) => {
      const { filters, toggle } = useCrossFilter();
      const result = (props.data ?? {}) as { columns?: string[]; rows?: Row[] };
      const columns = result.columns ?? [];
      const allRows = result.rows ?? [];
      // Alignment is judged over the full result, then the rows focus to the active selections.
      const numericColumns = columns.map((column) => isNumericColumn(allRows, column));
      const sourceRows = applyFilters(allRows, filters);
      if (sourceRows.length === 0) return <WidgetEmptyState />;
      const rows = sourceRows.map((row) => columns.map((column) => formatCell(row[column])));
      const rawRows = sourceRows.map((row) => columns.map((column) => row[column]));
      return (
        <DataTable
          columns={columns}
          rows={rows}
          numericColumns={numericColumns}
          rawRows={rawRows}
          onSelectCell={(column, value) => toggle(column, value)}
          activeValues={filters}
        />
      );
    },
  },
});
