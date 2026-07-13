import { memo } from "react";

import type { ArtifactVersionMeta } from "../types";

// The revision history panel for one artifact: every saved version, newest first. Clicking
// a version previews it; the one currently in effect carries a "current" badge; a previewed
// older version offers "Revert to this" (which the parent applies non-destructively).
export const VersionHistory = memo(function VersionHistory({
  versions,
  current,
  previewIndex,
  onPreview,
  onRevert,
}: {
  versions: ArtifactVersionMeta[];
  current: number;
  previewIndex: number | null;
  onPreview: (index: number) => void;
  onRevert: (index: number) => void;
}) {
  const shownIndex = previewIndex ?? current;
  return (
    <aside
      className="version-history shrink-0 overflow-y-auto p-3 bg-subtle border-l"
      aria-label="Version history"
    >
      <h3 className="m-0 mb-3 px-2 text-sm text-muted uppercase">History</h3>
      <ul className="flex flex-col gap-1 list-none m-0 p-0">
        {versions
          .slice()
          .reverse()
          .map((version) => (
            <li key={version.index}>
              <button
                type="button"
                className={
                  "version-history__item w-full text-left px-3 py-2 text-sm rounded-sm cursor-pointer" +
                  (version.index === shownIndex ? " version-history__item--active" : "")
                }
                onClick={() => onPreview(version.index)}
              >
                <span className="block truncate">
                  {version.instruction ?? "Original dashboard"}
                </span>
                {version.index === current && (
                  <span className="version-history__badge">current</span>
                )}
              </button>
              {previewIndex === version.index && version.index !== current && (
                <button
                  type="button"
                  className="version-history__revert w-full text-left px-3 py-2 text-sm cursor-pointer"
                  onClick={() => onRevert(version.index)}
                >
                  ↩ Revert to this version
                </button>
              )}
            </li>
          ))}
      </ul>
    </aside>
  );
});
