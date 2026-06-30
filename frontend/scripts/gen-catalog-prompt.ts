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
NEVER invent rows; the data is supplied separately.`;

const componentNames = catalog.componentNames as readonly string[];
const components = catalog.data.components as Record<
  string,
  { description?: string; example?: unknown }
>;

const componentLines = componentNames
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
