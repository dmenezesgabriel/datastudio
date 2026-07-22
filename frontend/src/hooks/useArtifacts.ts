import { useCallback, useEffect, useState } from "react";

import type {
  ArtifactDetail,
  ArtifactSummary,
  ArtifactVersionMeta,
  LoadState,
  SpecWithState,
} from "../types";

type ListPayload = {
  artifacts: {
    artifact_id: string;
    title: string;
    updated_at: number;
    version_count: number;
  }[];
};

type DetailPayload = {
  artifact_id: string;
  title: string;
  current: number;
  spec: SpecWithState;
  versions: { index: number; instruction: string | null; created_at: number }[];
};

function toSummary(a: ListPayload["artifacts"][number]): ArtifactSummary {
  return {
    id: a.artifact_id,
    title: a.title,
    updatedAt: a.updated_at,
    versionCount: a.version_count,
  };
}

function toDetail(payload: DetailPayload): ArtifactDetail {
  const versions: ArtifactVersionMeta[] = payload.versions.map((v) => ({
    index: v.index,
    instruction: v.instruction,
    createdAt: v.created_at,
  }));
  return {
    id: payload.artifact_id,
    title: payload.title,
    current: payload.current,
    spec: payload.spec,
    versions,
  };
}

// Read/write side of the artifact gallery: the list of saved dashboards plus save/delete.
// Best-effort like useConversations — a failed fetch leaves the gallery unchanged.
export function useArtifacts() {
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/artifacts");
      if (!response.ok) return;
      const payload = (await response.json()) as ListPayload;
      setArtifacts(payload.artifacts.map(toSummary));
    } catch {
      // Gallery is non-critical chrome; ignore transient network errors.
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const deleteArtifact = useCallback(
    async (id: string): Promise<void> => {
      try {
        await fetch(`/api/artifacts/${id}`, { method: "DELETE" });
        void refresh();
      } catch {
        // Non-critical; the gallery re-syncs on the next refresh.
      }
    },
    [refresh],
  );

  return { artifacts, refresh, deleteArtifact };
}

// One artifact's detail (current spec + history), with reload, revert, and version preview.
// The server owns the spec: after an edit or revert we re-fetch rather than patch locally,
// so what we render is always the deduped, persisted result.
//
// The result is a LoadState, not `ArtifactDetail | null`: /artifacts/:id is deep-linkable,
// so a 404 (deleted, or someone else's) must be reported as missing instead of painting a
// blank canvas forever.
export function useArtifact(id: string) {
  const [load, setLoad] = useState<LoadState<ArtifactDetail>>({ status: "loading" });

  const reload = useCallback(async () => {
    try {
      const response = await fetch(`/api/artifacts/${encodeURIComponent(id)}`);
      if (response.status === 404) return setLoad({ status: "missing" });
      if (!response.ok) return setLoad(keepIfLoaded({ status: "error" }));
      setLoad({ status: "ready", value: toDetail((await response.json()) as DetailPayload) });
    } catch {
      setLoad(keepIfLoaded({ status: "error" }));
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const revert = useCallback(
    async (index: number) => {
      try {
        const response = await fetch(`/api/artifacts/${id}/revert`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ index }),
        });
        if (!response.ok) return;
        setLoad({ status: "ready", value: toDetail((await response.json()) as DetailPayload) });
      } catch {
        // Ignore; the caller can retry.
      }
    },
    [id],
  );

  const loadVersion = useCallback(
    async (index: number): Promise<SpecWithState | null> => {
      try {
        const response = await fetch(`/api/artifacts/${id}/versions/${index}`);
        if (!response.ok) return null;
        const { spec } = (await response.json()) as { spec: SpecWithState };
        return spec;
      } catch {
        return null;
      }
    },
    [id],
  );

  return { load, reload, revert, loadVersion };
}

// A refresh that fails must not throw away a dashboard we are already showing — the user
// keeps reading the last-known version while the next attempt runs.
function keepIfLoaded(
  failure: LoadState<ArtifactDetail>,
): (previous: LoadState<ArtifactDetail>) => LoadState<ArtifactDetail> {
  return (previous) => (previous.status === "ready" ? previous : failure);
}
