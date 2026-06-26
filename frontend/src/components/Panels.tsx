import type { ReactNode } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";

/** Vertical container for the rendered view elements. */
export function Stack({ children }: { children?: ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>{children}</div>;
}

/** The natural-language answer, rendered as sanitized markdown (headings, bold, lists). */
export function Markdown({ text }: { text: string }) {
  const html = DOMPurify.sanitize(marked.parse(text, { async: false }));
  return (
    <div style={{ lineHeight: 1.5 }} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

/** A single headline metric with its caption. */
export function KpiStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 6, padding: "12px 16px" }}>
      <div style={{ fontSize: 24, fontWeight: 600 }}>{value}</div>
      <div style={{ fontSize: 13, color: "#666" }}>{label}</div>
    </div>
  );
}

/** The raw result rows rendered as a plain table. */
export function DataTable({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  return (
    <table style={{ borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column} style={cellStyle}>
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex}>
            {row.map((value, columnIndex) => (
              <td key={columnIndex} style={cellStyle}>
                {String(value)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const cellStyle = { border: "1px solid #ddd", padding: "6px 10px", textAlign: "left" } as const;
