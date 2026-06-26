import { defineCatalog } from "@json-render/core";
import { schema } from "@json-render/react/schema";
import { z } from "zod";

// The component vocabulary the backend may emit. These prop shapes are the
// client-side source of truth; the Python assembler (render_tree_builder.py)
// must emit elements that match them. No actions — the UI is presentational.
export const catalog = defineCatalog(schema, {
  components: {
    Stack: {
      props: z.object({}),
      description: "Vertical container that stacks its children.",
    },
    Markdown: {
      props: z.object({ text: z.string() }),
      description: "The natural-language answer rendered as text.",
    },
    KpiStat: {
      props: z.object({ label: z.string(), value: z.string() }),
      description: "A single headline metric with a caption.",
    },
    ChartJs: {
      props: z.object({
        kind: z.enum(["bar", "line", "pie"]),
        title: z.string(),
        labels: z.array(z.string()),
        datasets: z.array(
          z.object({ label: z.string(), data: z.array(z.number()) }),
        ),
      }),
      description: "A Chart.js chart (bar, line, or pie).",
    },
    DataTable: {
      props: z.object({
        columns: z.array(z.string()),
        rows: z.array(z.array(z.unknown())),
      }),
      description: "The raw result rows as a table.",
    },
  },
  // The presentation UI has no interactive actions.
  actions: {},
});
