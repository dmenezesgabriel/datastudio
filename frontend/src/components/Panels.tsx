import type { ReactNode } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";

/** Vertical container for the rendered view elements. */
export function Stack({ children }: { children?: ReactNode }) {
  return <div className="flex flex-col gap-4">{children}</div>;
}

/** The natural-language answer, rendered as sanitized markdown (headings, bold, lists). */
export function Markdown({ text }: { text: string }) {
  const html = DOMPurify.sanitize(marked.parse(text, { async: false }));
  return (
    <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

/** A single headline metric with its caption. */
export function KpiStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border rounded-sm px-4 py-3">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-sm text-muted">{label}</div>
    </div>
  );
}

/** The raw result rows rendered as a plain table. */
export function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: unknown[][];
}) {
  return (
    <table className="data-table text-base">
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column}>{column}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex}>
            {row.map((value, columnIndex) => (
              <td key={columnIndex}>{String(value)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
