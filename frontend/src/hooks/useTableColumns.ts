import { useEffect, useRef, useState } from "react";

// The columns of whichever table the composer is currently referring to. Fetched one table
// at a time, on demand — describing the whole catalog up front is what the backend's
// SqlEnginePort warns does not survive a warehouse-sized dataset.

/**
 * The column names of `table`, loaded the first time it is asked for and remembered after.
 *
 * Pass null when no table is being referred to. Each table is fetched once per composer:
 * the schema does not change while a question is being typed, and re-reading it on every
 * keystroke would put a request behind each one.
 *
 * Example:
 *     const columns = useTableColumns("events"); // ["amount", "category"]
 */
export function useTableColumns(table: string | null): string[] {
  const [byTable, setByTable] = useState<Record<string, string[]>>({});
  const requested = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (table === null || requested.current.has(table)) return;
    requested.current.add(table);
    void fetchColumnNames(table).then((columns) => {
      setByTable((loaded) => ({ ...loaded, [table]: columns }));
    });
  }, [table]);

  return table === null ? [] : (byTable[table] ?? []);
}

/** Read one table's column names, degrading to none rather than breaking the composer. */
async function fetchColumnNames(table: string): Promise<string[]> {
  try {
    const response = await fetch(`/api/schema/tables/${encodeURIComponent(table)}/columns`);
    if (!response.ok) return []; // includes the 404 for a table the dataset dropped
    const body: unknown = await response.json();
    return readColumnNames(body);
  } catch {
    // Offline, or the API is down. The composer still works; it just cannot suggest.
    return [];
  }
}

/** Narrow the response body to column names, tolerating a shape we did not expect. */
function readColumnNames(body: unknown): string[] {
  if (typeof body !== "object" || body === null) return [];
  const { columns } = body as { columns?: unknown };
  if (!Array.isArray(columns)) return [];
  return columns
    .map((column) => (column as { name?: unknown }).name)
    .filter((name): name is string => typeof name === "string");
}
