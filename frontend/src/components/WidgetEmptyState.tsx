/**
 * Shown in place of a widget when the active cross-filters leave it with no rows. A filtered
 * dashboard can reach an empty intersection (e.g. Category = Beverages AND Region = West with
 * no overlap); an explicit note — rather than a blank chart or table — keeps the user oriented
 * and points at the recovery (adjust or clear the filters). `role="status"` so assistive tech
 * hears it when a selection empties the widget (Nielsen: help users recognise/recover).
 */
export function WidgetEmptyState() {
  return (
    <div className="widget-empty" role="status">
      No rows match the current filters.
    </div>
  );
}
