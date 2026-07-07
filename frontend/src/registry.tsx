import { defineRegistry } from "@json-render/react";

import { catalog } from "./catalog";
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
import { WidgetFrame } from "./components/WidgetFrame";
import { formatCell, formatLabel, formatValue } from "./format";

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
    KpiStat: ({ props }) => {
      const rows = asRows(props.data);
      const row = rows[0];
      const value = row ? formatValue(row[props.valueColumn]) : "";
      const delta = row ? deltaFrom(row, props.deltaColumn, props.deltaLabel) : undefined;
      return <KpiStat label={props.label} value={value} delta={delta} />;
    },
    ChartJs: ({ props }) => {
      const rows = asRows(props.data);
      return (
        <ChartJsView
          kind={props.kind}
          title={props.title}
          labels={rows.map((row) => formatLabel(row[props.labelColumn]))}
          datasets={chartDatasets(rows, props.valueColumns)}
        />
      );
    },
    DataTable: ({ props }) => {
      const result = (props.data ?? {}) as { columns?: string[]; rows?: Row[] };
      const columns = result.columns ?? [];
      const rows = (result.rows ?? []).map((row) => columns.map((column) => formatCell(row[column])));
      return <DataTable columns={columns} rows={rows} />;
    },
  },
});
