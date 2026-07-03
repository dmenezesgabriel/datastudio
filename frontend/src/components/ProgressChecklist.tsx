import { Fragment } from "react";

import type { ProgressStatus, ProgressStep, ProgressSteps } from "../types";

// Glyph per step status — the "check it off when finished" affordance. Kept text-only
// (no icons/animation) so the signal reads instantly in light and dark.
const GLYPH: Record<ProgressStatus, string> = {
  pending: "○",
  running: "◔",
  done: "✓",
  failed: "✕",
};

// The live checklist of what the graph/LLM is doing, driven by the streamed progress
// steps. They render in pipeline order (their first-seen `order`), with each widget's
// sub-steps nested beneath its parent (Gestalt proximity → the group reads as one unit).
export function ProgressChecklist({ steps }: { steps?: ProgressSteps }) {
  if (!steps) return null;
  const ordered = Object.entries(steps).sort((a, b) => a[1].order - b[1].order);
  const topLevel = ordered.filter(([, step]) => !step.parentId);
  if (topLevel.length === 0) return null;

  return (
    <div
      className="mb-4 py-3 px-4 bg-subtle border rounded-md"
      aria-label="Progress"
      aria-live="polite"
    >
      <ul className="flex flex-col gap-1 list-none m-0 p-0">
        {topLevel.map(([id, step]) => (
          <Fragment key={id}>
            <ChecklistItem step={step} />
            {ordered
              .filter(([, child]) => child.parentId === id)
              .map(([childId, child]) => (
                <ChecklistItem key={childId} step={child} child />
              ))}
          </Fragment>
        ))}
      </ul>
    </div>
  );
}

function ChecklistItem({
  step,
  child,
}: {
  step: ProgressStep;
  child?: boolean;
}) {
  const classes = [
    "checklist__item flex items-center gap-2 text-base",
    child ? "checklist__item--child" : "",
    step.status === "pending" ? "checklist__item--pending" : "",
  ].join(" ");
  return (
    <li className={classes}>
      <span
        className={`checklist__glyph checklist__glyph--${step.status}`}
        aria-hidden="true"
      >
        {GLYPH[step.status]}
      </span>
      {step.label}
    </li>
  );
}
