// The table picker that opens on "@". Sits above the composer box rather than floating at
// the caret: a docked panel needs no coordinate maths, cannot be clipped by the transcript,
// and reads the same at every window width.
export function MentionMenu({
  id,
  matches,
  highlighted,
  onPick,
}: {
  id: string;
  matches: string[];
  /** Index into `matches` the keyboard is on; the mouse follows it too. */
  highlighted: number;
  onPick: (table: string) => void;
}) {
  if (matches.length === 0) return null;

  return (
    <ul id={id} role="listbox" aria-label="Tables" className="composer__menu list-none m-0">
      {matches.map((table, index) => (
        <li
          key={table}
          id={optionId(id, index)}
          role="option"
          aria-selected={index === highlighted}
          className={
            "composer__menu-item px-3 py-2 text-base cursor-pointer" +
            (index === highlighted ? " composer__menu-item--on" : "")
          }
          // The editor must keep the caret: losing focus to the menu would close it before
          // the click ever lands, so the press is prevented and the click does the work.
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onPick(table)}
        >
          {table}
        </li>
      ))}
    </ul>
  );
}

/**
 * The DOM id of one option, so the field can point aria-activedescendant at it.
 *
 * Example:
 *     optionId("composer-table-menu", 0); // "composer-table-menu-option-0"
 */
export function optionId(menuId: string, index: number): string {
  return `${menuId}-option-${index}`;
}
