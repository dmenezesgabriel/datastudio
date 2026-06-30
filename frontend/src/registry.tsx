import { defineRegistry } from "@json-render/react";

import { catalog } from "./catalog";
import { ChartJsView, type ChartDataset } from "./components/ChartJsView";
import { DataTable, KpiStat, Markdown, Stack } from "./components/Panels";

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
    data: rows.map((row) => Number(row[column])),
  }));
}

export const { registry } = defineRegistry(catalog, {
  components: {
    Stack: ({ children }) => <Stack>{children}</Stack>,
    Markdown: ({ props }) => <Markdown text={props.text} />,
    KpiStat: ({ props }) => {
      const rows = asRows(props.data);
      const value = rows.length ? String(rows[0][props.valueColumn] ?? "") : "";
      return <KpiStat label={props.label} value={value} />;
    },
    ChartJs: ({ props }) => {
      const rows = asRows(props.data);
      return (
        <ChartJsView
          kind={props.kind}
          title={props.title}
          labels={rows.map((row) => String(row[props.labelColumn]))}
          datasets={chartDatasets(rows, props.valueColumns)}
        />
      );
    },
    DataTable: ({ props }) => {
      const result = (props.data ?? {}) as { columns?: string[]; rows?: Row[] };
      const columns = result.columns ?? [];
      const rows = (result.rows ?? []).map((row) => columns.map((column) => row[column]));
      return <DataTable columns={columns} rows={rows} />;
    },
  },
});
