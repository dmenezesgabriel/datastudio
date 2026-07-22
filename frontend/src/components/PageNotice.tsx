import type { ReactNode } from "react";

// The centred "nothing to show here" panel: an empty chat, a dead link, a failed load.
// Shared so every dead end in the app reads the same way (and so the heading level stays
// h2, nesting correctly under the sidebar's h1).
export function PageNotice({ heading, children }: { heading: string; children?: ReactNode }) {
  return (
    <div className="page-notice flex-1 overflow-y-auto py-6 px-4">
      <div className="page-notice__body text-center text-muted">
        <h2>{heading}</h2>
        {children}
      </div>
    </div>
  );
}
