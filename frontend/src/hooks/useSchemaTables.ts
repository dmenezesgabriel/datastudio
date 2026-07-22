import { useCallback, useRef, useState } from "react";

// The dataset's table names, for the composer's "@" menu. Fetched once and held for the
// life of the composer: the schema does not change while a question is being typed, and the
// menu has to be populated before the user finishes typing the name they are after.

/**
 * The dataset's table names, loaded on demand.
 *
 * `load` is idempotent — call it as early as the field is focused (what claude.ai does with
 * its mention providers) so the list is already there by the time "@" is typed.
 *
 * Example:
 *     const { tables, load } = useSchemaTables();
 *     <div onFocus={load} />
 */
export function useSchemaTables(): { tables: string[]; load: () => void } {
  const [tables, setTables] = useState<string[]>([]);
  const started = useRef(false);

  const load = useCallback(() => {
    if (started.current) return;
    started.current = true;
    void fetchTableNames().then(setTables);
  }, []);

  return { tables, load };
}

/** Read the table names, degrading to none rather than breaking the composer. */
async function fetchTableNames(): Promise<string[]> {
  try {
    const response = await fetch("/api/schema/tables");
    if (!response.ok) return [];
    const body: unknown = await response.json();
    return readTableNames(body);
  } catch {
    // Offline, or the API is down. The composer still works; it just cannot suggest.
    return [];
  }
}

/** Narrow the response body to table names, tolerating a shape we did not expect. */
function readTableNames(body: unknown): string[] {
  if (typeof body !== "object" || body === null) return [];
  const { tables } = body as { tables?: unknown };
  if (!Array.isArray(tables)) return [];
  return tables.filter((name): name is string => typeof name === "string");
}
