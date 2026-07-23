import { useEffect, useRef } from "react";

// The picker that opens on "@". Sits above the composer box rather than floating at the caret:
// a docked panel needs no coordinate maths, cannot be clipped by the transcript, and reads the
// same at every window width. It lists tables first; a table can be drilled into its columns,
// which the chevron and the hint line advertise so the gesture is discoverable rather than lore.
export function MentionMenu({
  id,
  label,
  hint,
  matches,
  highlighted,
  onPick,
  onDrill,
}: {
  id: string;
  /** Announces what the list holds — "Tables" while browsing tables, "Columns of X" after a drill. */
  label: string;
  /** The one-line affordance under the list, e.g. how to reach columns. */
  hint: string;
  matches: string[];
  /** Index into `matches` the keyboard is on; the mouse follows it too. */
  highlighted: number;
  onPick: (name: string) => void;
  /** Given only for drillable rows (tables): opens `name`'s columns instead of committing it. */
  onDrill?: (name: string) => void;
}) {
  // Only the highlighted option's name carries this, so it always points at the one to reveal.
  // The name rather than the whole row, so the chevron is never what gets scrolled to.
  const highlightedName = useRef<HTMLSpanElement>(null);

  // The list scrolls past about seven rows: without this, arrowing to the eighth — or
  // wrapping from the top round to the bottom — leaves aria-activedescendant pointing at an
  // option nobody can see. "nearest" so an option already in view is not jerked around.
  useEffect(() => {
    highlightedName.current?.scrollIntoView({ block: "nearest" });
  }, [highlighted, matches]);

  if (matches.length === 0) return null;

  return (
    <div className="composer__menu-panel">
      <ul id={id} role="listbox" aria-label={label} className="composer__menu list-none m-0">
        {matches.map((name, index) => (
          <li
            key={name}
            id={optionId(id, index)}
            role="option"
            aria-selected={index === highlighted}
            className={
              "composer__menu-item flex items-center px-3 py-2 text-base cursor-pointer" +
              (index === highlighted ? " composer__menu-item--on" : "")
            }
            // The editor must keep the caret: losing focus to the menu would close it before
            // the click ever lands, so the press is prevented and the click does the work.
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onPick(name)}
          >
            <span
              ref={index === highlighted ? highlightedName : null}
              className="composer__menu-name flex-1"
            >
              {name}
            </span>
            {onDrill !== undefined && (
              <button
                type="button"
                className="composer__menu-drill"
                // Named for the row, so a screen-reader user knows which table it drills into;
                // not a tab stop, since the whole menu is driven from the editor's caret.
                aria-label={`Show columns of ${name}`}
                tabIndex={-1}
                onMouseDown={(event) => event.preventDefault()}
                onClick={(event) => {
                  event.stopPropagation(); // drill, don't also let the row commit the table
                  onDrill(name);
                }}
              >
                ›
              </button>
            )}
          </li>
        ))}
      </ul>
      {/* Reinforces the chevron in words. aria-hidden: the chevron buttons already carry the
          accessible name for the drill, so this line would only repeat it out of the list. */}
      <div className="composer__menu-hint" aria-hidden="true">
        {hint}
      </div>
    </div>
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
