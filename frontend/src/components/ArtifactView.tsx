import { useCallback, useState } from "react";
import { useUIStream } from "@json-render/react";
import { Link } from "react-router-dom";

import { DashboardCanvas } from "./DashboardCanvas";
import { Composer } from "./Composer";
import { PageNotice } from "./PageNotice";
import { ProgressChecklist } from "./ProgressChecklist";
import { VersionHistory } from "./VersionHistory";
import { useArtifact } from "../hooks/useArtifacts";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { ARTIFACTS_PATH } from "../routes";
import type { SpecWithState } from "../types";

// One saved dashboard, opened for viewing and conversational editing. The rendered spec is
// the server's — after an edit or revert we re-fetch rather than apply patches locally, so
// what shows is always the deduped, persisted result (the edit stream is used only for its
// lifecycle and live progress). Keyed by artifact id upstream so it remounts per artifact.
export function ArtifactView({ artifactId }: { artifactId: string }) {
  const { load, reload, revert, loadVersion } = useArtifact(artifactId);
  const detail = load.status === "ready" ? load.value : null;
  useDocumentTitle(detail?.title ?? null);
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [previewSpec, setPreviewSpec] = useState<SpecWithState | null>(null);

  const { spec: editSpec, isStreaming, send, clear } = useUIStream({
    api: `/api/artifacts/${artifactId}/edit`,
    onComplete: () => {
      // The server has persisted the new version; drop any preview and re-fetch the truth.
      setPreviewIndex(null);
      setPreviewSpec(null);
      clear();
      void reload();
    },
  });

  const applyEdit = useCallback(
    (instruction: string) => {
      if (isStreaming) return;
      void send(instruction, {});
    },
    [isStreaming, send],
  );

  const preview = useCallback(
    async (index: number) => {
      if (!detail || index === detail.current) {
        setPreviewIndex(null);
        setPreviewSpec(null);
        return;
      }
      setPreviewIndex(index);
      setPreviewSpec(await loadVersion(index));
    },
    [detail, loadVersion],
  );

  const onRevert = useCallback(
    async (index: number) => {
      setPreviewIndex(null);
      setPreviewSpec(null);
      await revert(index);
    },
    [revert],
  );

  const shownSpec = previewIndex !== null ? previewSpec : (detail?.spec ?? null);
  const progress = (editSpec as SpecWithState | null)?.state?.progress;

  // A shared link outlives the dashboard it points at (deleted, or another user's), so the
  // 404 has to say so rather than render an empty canvas under a generic title.
  if (load.status === "missing") {
    return (
      <main className="main">
        <PageNotice heading="This dashboard isn’t available">
          <p>It may have been deleted, or it belongs to someone else.</p>
          <Link className="text-base" to={ARTIFACTS_PATH}>
            Back to saved dashboards
          </Link>
        </PageNotice>
      </main>
    );
  }

  return (
    <main className="main">
      <header className="artifact-view__header flex items-center gap-3 px-4 py-3 border-b">
        <Link
          className="artifact-view__back shrink-0 px-3 py-2 text-sm border rounded-md cursor-pointer"
          to={ARTIFACTS_PATH}
        >
          ← Artifacts
        </Link>
        <h2 className="m-0 text-lg font-semibold truncate">{detail?.title ?? "Artifact"}</h2>
      </header>
      <div className="artifact-view__body flex flex-1 min-h-0">
        <div className="artifact-view__canvas flex-1 overflow-y-auto py-6 px-4">
          <div className="max-w-content mx-auto min-w-0">
            {isStreaming && <ProgressChecklist steps={progress} />}
            {previewIndex !== null && (
              <p className="artifact-view__preview-note mb-3 text-sm text-muted">
                Viewing an earlier version — revert from the history panel to restore it.
              </p>
            )}
            <DashboardCanvas spec={shownSpec} loading={isStreaming} />
          </div>
        </div>
        {detail && (
          <VersionHistory
            versions={detail.versions}
            current={detail.current}
            previewIndex={previewIndex}
            onPreview={preview}
            onRevert={onRevert}
          />
        )}
      </div>
      <Composer
        onSubmit={applyEdit}
        disabled={isStreaming}
        draftKey={`artifact:${artifactId}`}
        placeholder="Describe a change — e.g. make the revenue chart a line chart…"
        label="Edit"
      />
    </main>
  );
}
