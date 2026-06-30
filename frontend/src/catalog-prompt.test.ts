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

test("generated catalog prompt is in sync with the catalog", () => {
  const prompt = readFileSync(PROMPT_PATH, "utf8");
  const names = catalog.componentNames as readonly string[];
  const components = catalog.data.components as Record<string, { example?: unknown }>;

  for (const name of names) {
    expect(prompt, `prompt is missing component ${name} — run npm run gen:prompt`).toContain(name);
    const example = JSON.stringify(components[name]?.example ?? {});
    expect(prompt, `prompt is missing the ${name} example — run npm run gen:prompt`).toContain(
      example,
    );
  }
});
