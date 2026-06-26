import { defineRegistry } from "@json-render/react";

import { catalog } from "./catalog";
import { ChartJsView } from "./components/ChartJsView";
import { DataTable, KpiStat, Markdown, Stack } from "./components/Panels";

// Bind each catalogue component name to its React implementation. Prop types are
// inferred from the Zod schemas in catalog.ts, so these stay type-checked.
export const { registry } = defineRegistry(catalog, {
  components: {
    Stack: ({ children }) => <Stack>{children}</Stack>,
    Markdown: ({ props }) => <Markdown text={props.text} />,
    KpiStat: ({ props }) => <KpiStat label={props.label} value={props.value} />,
    ChartJs: ({ props }) => (
      <ChartJsView
        kind={props.kind}
        title={props.title}
        labels={props.labels}
        datasets={props.datasets}
      />
    ),
    DataTable: ({ props }) => <DataTable columns={props.columns} rows={props.rows} />,
  },
});
