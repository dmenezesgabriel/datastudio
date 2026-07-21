import { useId, useState, type ReactNode } from "react";

/** Wraps one widget's visualization with the SQL that produced it, exposing a small
 *  icon toggle in its own row above the widget. Backend-owned (never authored by the
 *  model): the serializer wraps every widget in one and fills `sql` via a `/props/sql`
 *  patch. With no SQL (e.g. the query failed) it renders the widget alone, no toggle.
 *
 *  The control used to be a Preview/SQL pill absolutely positioned over the widget's
 *  top-right corner. Hidden until hover it was undiscoverable and unreachable on touch
 *  (audit MOD-4); always visible it covered widget content — a KPI's headline figure,
 *  a table's last column header — which `padding-top` on the body only papered over.
 *  Both failures came from overlaying, so the toggle now sits in flow above the body:
 *  it cannot overlap what it sits beside, and for a KPI it lands outside the tile border.
 *
 *  Example:
 *    <WidgetFrame sql="SELECT count(*) FROM events"><ChartJsView … /></WidgetFrame>
 */
export function WidgetFrame({ sql, children }: { sql: string; children?: ReactNode }) {
  const [showingSql, setShowingSql] = useState(false);
  const bodyId = useId();
  if (!sql) return <div className="widget-frame">{children}</div>;
  return (
    <div className="widget-frame">
      <div className="widget-frame__tools">
        <SqlToggle showingSql={showingSql} bodyId={bodyId} onToggle={setShowingSql} />
      </div>
      <div className="widget-frame__body" id={bodyId}>
        {showingSql ? (
          // A long query scrolls inside its own box (it would otherwise spill over the
          // next grid cell). A scrollable region needs keyboard access to be reachable,
          // hence tabIndex + a name — the same treatment DataTable's .table-scroll gets
          // (WCAG 2.1.1, a11y audit exhaustive-check finding).
          <pre className="widget-frame__sql" tabIndex={0} role="group" aria-label="SQL query">
            <code>{sql}</code>
          </pre>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/** The icon-only toggle. `aria-pressed` carries the state, so the accessible name stays
 *  constant — swapping it as well would double-encode the state and announce it twice. */
function SqlToggle({
  showingSql,
  bodyId,
  onToggle,
}: {
  showingSql: boolean;
  bodyId: string;
  onToggle: (showingSql: boolean) => void;
}) {
  return (
    <button
      type="button"
      className="widget-frame__sql-toggle"
      aria-label="Show SQL"
      title="Show SQL"
      aria-pressed={showingSql}
      aria-controls={bodyId}
      onClick={() => onToggle(!showingSql)}
    >
      <CodeGlyph />
    </button>
  );
}

/** The `</>` mark. Decorative: the button carries the name, so it stays out of the
 *  accessibility tree (an exposed <svg> would read as a second, nameless node). */
function CodeGlyph() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M9 18 3 12l6-6" />
      <path d="m15 6 6 6-6 6" />
    </svg>
  );
}
