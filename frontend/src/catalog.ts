import { defineCatalog } from "@json-render/core";
import { schema } from "@json-render/react/schema";
import { z } from "zod";

// The component vocabulary the LLM may emit as a json-render SpecStream. The LLM
// authors the structure; data props are bound to the query result via $state
// (e.g. {"$state":"/result/rows"}) so values never pass through the model — the
// backend streams the rows as /state patches. `data` is `unknown` because its
// value in the spec is a $state binding, resolved to real rows at render time.
//
// This catalog is the SINGLE SOURCE OF TRUTH for the backend prompt: the `example`
// values below are emitted verbatim by `catalog.prompt()`, which `npm run gen:prompt`
// writes to the prompt the Python view node loads. Keep the registry in sync too.
export const catalog = defineCatalog(schema, {
  components: {
    Stack: {
      props: z.object({}),
      description: "Vertical container that stacks its children.",
      example: {},
    },
    Markdown: {
      props: z.object({ text: z.string() }),
      description: "A short note rendered as markdown text.",
      example: { text: "A short note." },
    },
    KpiStat: {
      props: z.object({
        label: z.string(),
        valueColumn: z.string(),
        data: z.unknown(),
      }),
      description:
        "A single headline metric (single-row results only). valueColumn names the result " +
        "column holding the number; bind data to the result rows.",
      example: { label: "Total orders", valueColumn: "order_count", data: { $state: "/result/rows" } },
    },
    ChartJs: {
      props: z.object({
        kind: z.enum(["bar", "line", "pie"]),
        title: z.string(),
        labelColumn: z.string(),
        valueColumns: z.array(z.string()),
        data: z.unknown(),
      }),
      description:
        "A Chart.js chart. labelColumn = category/time column; valueColumns = numeric series " +
        "columns. Use line for a time series, bar for categories or rankings, pie only for a " +
        "parts-of-a-whole breakdown of at most 5 slices.",
      example: {
        kind: "bar",
        title: "Revenue by month",
        labelColumn: "month",
        valueColumns: ["revenue"],
        data: { $state: "/result/rows" },
      },
    },
    DataTable: {
      props: z.object({ data: z.unknown() }),
      description: "The raw result rows as a table.",
      example: { data: { $state: "/result" } },
    },
  },
  // No interactive actions: data arrives as streamed /state patches, not via an action.
  actions: {},
});
