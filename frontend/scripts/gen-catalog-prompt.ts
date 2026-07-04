// Generates the backend's view-authoring system prompt FROM the json-render catalog
// (the single source of truth). The component vocabulary — names, descriptions, and
// $state-bound prop examples — is read from the catalog so it can never drift from
// what actually renders. The constrained framing (author ONE widget, never invent
// data) is fixed here because the default catalog.prompt() template assumes an app
// that mints its own sample /state, which is the opposite of our flow.
//
// Run with `npm run gen:prompt`; a pre-commit hook regenerates and diffs the output.
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { catalog } from "../src/catalog";

const HEADER =
  "# GENERATED FROM frontend/src/catalog.ts BY `npm run gen:prompt` — DO NOT EDIT BY HAND.";

const FRAMING = `You author ONE data-visualization element for a dashboard widget as a json-render
SpecStream: RFC-6902 JSON-Patch lines, one JSON object per line, and NOTHING else
(no prose, no code fences). Add your element and append it to the root's children:

  {"op":"add","path":"/elements/<id>","value":{"type":"<Component>","props":{...},"children":[]}}
  {"op":"add","path":"/elements/root/children/-","value":"<id>"}

DATA: you never see or emit data values. Bind every data prop to the result with
{"$state":"/result/rows"} (an array of row objects) — or {"$state":"/result"} for a
table — and reference columns by their exact names. NEVER emit /state patches and
NEVER invent rows; the data is supplied separately.

SELECTION GUIDANCE: choose the element that best fits the result shape, following
data-visualization best practices.
- A single-row result (one headline number) -> KpiStat.
- A category or time column plus a numeric series -> ChartJs. Pick the kind by the x-axis:
  line for a time/ordered axis, bar for unordered categories or rankings, pie ONLY for a
  parts-of-a-whole breakdown with at most 5 slices.
- A wide result (many columns) or a long detail/lookup list -> DataTable.
- valueColumns: chart the ONE measure that answers this widget. Put multiple columns in
  valueColumns ONLY when they share a unit and scale (e.g. two comparable counts). If the
  result has measures of different units or magnitudes (e.g. a count AND a monetary total),
  chart the primary one and leave the other out — a table can show both.
ANTI-PATTERNS (never do these): a pie with more than 5 slices (use bar or a table); a line
chart for unordered categories; a KpiStat for a multi-row result; two series of different
units or wildly different scales on one chart (one axis can't serve both — pick one).`;

// Backend-owned components, not authored per-widget: the F-layout containers (root
// Stack, KpiRow band, Grid region) the backend assembles deterministically, plus the
// WidgetFrame the backend wraps each widget in (it carries the widget's SQL). The
// per-widget author only emits ONE leaf visualization, so these are omitted from the
// authorable vocabulary below.
const LAYOUT_CONTAINERS = new Set(["Stack", "KpiRow", "Grid", "WidgetFrame"]);

const componentNames = catalog.componentNames as readonly string[];
const components = catalog.data.components as Record<
  string,
  { description?: string; example?: unknown }
>;

const componentLines = componentNames
  .filter((name) => !LAYOUT_CONTAINERS.has(name))
  .map((name) => {
    const def = components[name] ?? {};
    return `- ${name} — ${def.description ?? ""}\n  example: ${JSON.stringify(def.example ?? {})}`;
  })
  .join("\n");

const prompt = `${HEADER}

${FRAMING}

AVAILABLE COMPONENTS (use only these types):
${componentLines}
`;

const here = dirname(fileURLToPath(import.meta.url));
const outPath = resolve(
  here,
  "../../src/chat/infrastructure/graph/prompts/catalog_prompt.generated.txt",
);

writeFileSync(outPath, prompt, "utf8");
console.log(`wrote ${outPath}`);
