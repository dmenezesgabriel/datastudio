import type { Spec } from "@json-render/react";

// The stream carries /elements patches (the LLM-authored widgets) and /state patches
// (each widget's rows). The live checklist rides a reserved `state.progress` key — the
// json-render client only applies /state and /elements patches, so progress can't be a
// top-level channel. useUIStream flattens all of it onto `spec.state`.
export type SpecWithState = Spec & {
  state?: Record<string, unknown> & { progress?: ProgressSteps };
};

// One completed exchange in the transcript: the question asked and the dashboard produced.
export type Turn = { prompt: string; spec: SpecWithState };

// A thread as shown in the sidebar. `title` is the recognisable label (first question).
export type ThreadSummary = { id: string; title: string };

// A saved dashboard as shown in the gallery.
export type ArtifactSummary = {
  id: string;
  title: string;
  updatedAt: number;
  versionCount: number;
};

// One entry in an artifact's revision history. `instruction` is the edit that produced
// it (null for the first saved version); it labels the version in the history panel.
export type ArtifactVersionMeta = {
  index: number;
  instruction: string | null;
  createdAt: number;
};

// A saved dashboard opened for viewing/editing: its current spec plus its full history.
export type ArtifactDetail = {
  id: string;
  title: string;
  current: number;
  spec: SpecWithState;
  versions: ArtifactVersionMeta[];
};

// A step in the live checklist. Steps arrive keyed by id under `state.progress`.
export type ProgressStatus = "pending" | "running" | "done" | "failed";
export type ProgressStep = {
  label: string;
  status: ProgressStatus;
  parentId?: string | null;
  order: number;
};
export type ProgressSteps = Record<string, ProgressStep>;
