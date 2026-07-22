import { memo, useState } from "react";
import { Link } from "react-router-dom";

import { PageNotice } from "./PageNotice";
import { artifactPath } from "../routes";
import type { ArtifactSummary } from "../types";

// The gallery of saved dashboards. Each card links to its artifact for viewing/editing.
// Empty until the user saves a dashboard from a chat answer.
export const ArtifactGallery = memo(function ArtifactGallery({
  artifacts,
  onDelete,
}: {
  artifacts: ArtifactSummary[];
  onDelete: (id: string) => void;
}) {
  if (artifacts.length === 0) {
    return (
      <PageNotice heading="No saved dashboards yet">
        <p>Save a dashboard from a chat answer to keep and edit it here.</p>
      </PageNotice>
    );
  }

  return (
    <div className="artifact-gallery flex-1 overflow-y-auto py-6 px-4">
      {/* A heading so the gallery's h3 cards nest under an h2, not directly under the
          sidebar h1 — the outline was skipping a level (a11y audit QW-9). */}
      <h2 className="artifact-gallery__heading max-w-content mx-auto mb-4 text-lg font-semibold">
        Saved dashboards
      </h2>
      <div className="artifact-gallery__grid">
        {artifacts.map((artifact) => (
          <ArtifactCard key={artifact.id} artifact={artifact} onDelete={onDelete} />
        ))}
      </div>
    </div>
  );
});

// One gallery card. Delete is destructive and irreversible, so it's a two-step action:
// the first click arms a confirm prompt rather than deleting outright (a11y audit QW-6).
function ArtifactCard({
  artifact,
  onDelete,
}: {
  artifact: ArtifactSummary;
  onDelete: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <article className="artifact-card flex flex-col gap-2 p-4 bg-raised border rounded-md">
      <h3 className="m-0 text-base font-semibold truncate" title={artifact.title}>
        {artifact.title}
      </h3>
      <p className="m-0 text-sm text-muted">
        {artifact.versionCount} {artifact.versionCount === 1 ? "version" : "versions"}
      </p>
      {confirming ? (
        <div className="artifact-card__actions flex gap-2 items-center">
          <span className="text-sm">Delete this dashboard?</span>
          <button
            type="button"
            className="artifact-card__delete px-3 py-2 text-sm font-medium rounded-md cursor-pointer"
            aria-label={`Confirm deleting ${artifact.title}`}
            onClick={() => onDelete(artifact.id)}
          >
            Confirm
          </button>
          <button
            type="button"
            className="artifact-card__open px-3 py-2 text-sm border rounded-md cursor-pointer"
            onClick={() => setConfirming(false)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="artifact-card__actions flex gap-2">
          {/* A link, not a button: a saved dashboard is an address, so it can be opened in
              a new tab or copied. The title is in the accessible name because a grid of
              cards otherwise offers a row of identical "Open" controls (a11y audit QW-9). */}
          <Link
            className="artifact-card__open px-3 py-2 text-sm font-medium border rounded-md cursor-pointer"
            to={artifactPath(artifact.id)}
            aria-label={`Open ${artifact.title}`}
          >
            Open
          </Link>
          <button
            type="button"
            className="artifact-card__delete px-3 py-2 text-sm rounded-md cursor-pointer"
            onClick={() => setConfirming(true)}
          >
            Delete
          </button>
        </div>
      )}
    </article>
  );
}
