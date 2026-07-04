import { useState, type ReactNode } from "react";

type FrameMode = "preview" | "sql";

/** Wraps one widget's visualization with the SQL that produced it, exposing a top-left
 *  Preview/SQL toggle. Backend-owned (never authored by the model): the serializer wraps
 *  every widget in one and fills `sql` via a `/props/sql` patch. With no SQL (e.g. the
 *  query failed) it renders the widget alone, no toggle.
 *
 *  Example:
 *    <WidgetFrame sql="SELECT count(*) FROM events"><ChartJsView … /></WidgetFrame>
 */
export function WidgetFrame({ sql, children }: { sql: string; children?: ReactNode }) {
  const [mode, setMode] = useState<FrameMode>("preview");
  if (!sql) return <div className="widget-frame">{children}</div>;
  return (
    <div className="widget-frame">
      <div className="widget-frame__toggle" role="group" aria-label="Widget view">
        <FrameTab mode="preview" active={mode} onSelect={setMode}>
          Preview
        </FrameTab>
        <FrameTab mode="sql" active={mode} onSelect={setMode}>
          SQL
        </FrameTab>
      </div>
      <div className="widget-frame__body">
        {mode === "sql" ? (
          <pre className="widget-frame__sql">
            <code>{sql}</code>
          </pre>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/** One segment of the Preview/SQL toggle; `aria-pressed` carries selection (not color alone). */
function FrameTab({
  mode,
  active,
  onSelect,
  children,
}: {
  mode: FrameMode;
  active: FrameMode;
  onSelect: (mode: FrameMode) => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className="widget-frame__tab"
      aria-pressed={mode === active}
      onClick={() => onSelect(mode)}
    >
      {children}
    </button>
  );
}
