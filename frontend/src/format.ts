/** Presentation formatting shared by the KPI card and chart axis labels. */

const NUMBER_FMT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

// DuckDB date_trunc / date columns arrive as ISO-8601 (the backend serializes
// temporals with isoformat), so a monthly axis label is e.g. "2017-01-01T00:00:00".
// Rendered raw, Chart.js shows the meaningless time part; we collapse midnight
// timestamps to the date so a monthly/daily axis reads as a date.
const ISO_MIDNIGHT = /^(\d{4}-\d{2}-\d{2})T00:00:00(?:\.0+)?(?:Z|[+-]\d{2}:?\d{2})?$/;

/**
 * Format a KPI / headline value: numbers (or numeric strings) get thousands
 * separators and at most two decimals, so 16008872.1199 renders "16,008,872.12"
 * and 160.99026 renders "160.99". Non-numeric values are returned unchanged;
 * null/undefined render as an empty string.
 *
 * @example
 *   formatValue(99441)        // "99,441"
 *   formatValue("160.99026")  // "160.99"
 *   formatValue("credit_card")// "credit_card"
 */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  // A non-finite number (NaN from a divide-by-zero ratio, Infinity from an aggregate over
  // zero rows) has no meaningful figure — render blank rather than the literal "NaN"/"∞".
  if (typeof value === "number") return Number.isFinite(value) ? NUMBER_FMT.format(value) : "";
  const num = numericOrNull(value);
  return num === null ? String(value) : NUMBER_FMT.format(num);
}

function numericOrNull(value: unknown): number | null {
  if (typeof value !== "string" || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Whether a raw cell reads as a number (a finite number, or a numeric string like
 * "160.99"). Drives right-alignment of numeric table columns — a measure column
 * aligns on the decimal, a text column stays left. null/empty are neutral (false).
 *
 * @example
 *   isNumeric(2017)          // true
 *   isNumeric("160.99026")   // true
 *   isNumeric("credit_card") // false
 */
export function isNumeric(value: unknown): boolean {
  if (typeof value === "number") return Number.isFinite(value);
  return numericOrNull(value) !== null;
}

/**
 * Format a data-table cell. Fractional numbers (measures like a summed total) get
 * thousands separators and at most two decimals, so a float-precision artifact like
 * 16008872.119998764 reads "16,008,872.12". Integers are left plain on purpose —
 * grouping a year (2017) or an id would corrupt it — and non-numbers pass through.
 *
 * @example
 *   formatCell(16008872.119998764) // "16,008,872.12"
 *   formatCell(2017)               // "2017"  (year — no grouping)
 *   formatCell("credit_card")      // "credit_card"
 */
export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return ""; // NaN/Infinity have no cell representation
    return Number.isInteger(value) ? String(value) : NUMBER_FMT.format(value);
  }
  return String(value);
}

/**
 * Whether a column reads as numeric across a result: it has values and every non-empty cell
 * is a number (or numeric string). Drives right-alignment of measure columns, and marks a
 * column as a measure (not a filterable dimension). Ids and years count as numeric — correct.
 *
 * @example
 *   isNumericColumn([{ amount: 12 }, { amount: "3.5" }], "amount") // true
 *   isNumericColumn([{ city: "Rio" }], "city")                     // false
 */
export function isNumericColumn(rows: Record<string, unknown>[], column: string): boolean {
  const present = rows
    .map((row) => row[column])
    .filter((value) => value !== null && value !== undefined && value !== "");
  return present.length > 0 && present.every(isNumeric);
}

/**
 * Format a chart axis label. A midnight ISO timestamp (DuckDB date_trunc output)
 * renders as its date alone so a monthly axis reads "2017-01-01" instead of the
 * meaningless "0:00:00"; every other value is stringified unchanged.
 *
 * @example
 *   formatLabel("2017-01-01T00:00:00") // "2017-01-01"
 *   formatLabel("credit_card")         // "credit_card"
 */
export function formatLabel(value: unknown): string {
  if (value === null || value === undefined) return ""; // a null category is a blank axis tick, not "null"
  if (typeof value === "string") {
    const midnight = value.match(ISO_MIDNIGHT);
    if (midnight) return midnight[1];
  }
  return String(value);
}
