import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "vitest";

import { catalog } from "./catalog";

// Guards against the generated backend prompt drifting from the catalog. The
// pre-commit hook regenerates it; this fails fast in `npm test` if a component
// or its $state example changed without `npm run gen:prompt` being re-run.
const PROMPT_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../src/chat/infrastructure/graph/prompts/catalog_prompt.generated.txt",
);

// Backend-owned components (F-layout containers + the per-widget WidgetFrame) are not
// authored per-widget, so gen-catalog-prompt omits them from the authorable vocabulary.
// Keep this in sync with LAYOUT_CONTAINERS there.
const LAYOUT_CONTAINERS = new Set(["Stack", "KpiRow", "Grid", "WidgetFrame"]);

test("generated catalog prompt is in sync with the catalog", () => {
  const prompt = readFileSync(PROMPT_PATH, "utf8");
  const names = catalog.componentNames as readonly string[];
  const components = catalog.data.components as Record<string, { example?: unknown }>;

  for (const name of names) {
    if (LAYOUT_CONTAINERS.has(name)) continue;
    expect(prompt, `prompt is missing component ${name} — run npm run gen:prompt`).toContain(name);
    const example = JSON.stringify(components[name]?.example ?? {});
    expect(prompt, `prompt is missing the ${name} example — run npm run gen:prompt`).toContain(
      example,
    );
  }
});

test("layout containers are excluded from the authorable component list", () => {
  const prompt = readFileSync(PROMPT_PATH, "utf8");
  const authorable = prompt.slice(prompt.indexOf("AVAILABLE COMPONENTS"));
  for (const container of LAYOUT_CONTAINERS) {
    expect(authorable, `${container} must not be offered to the per-widget author`).not.toContain(
      `- ${container} —`,
    );
  }
});
