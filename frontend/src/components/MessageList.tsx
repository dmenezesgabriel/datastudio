import { useMemo } from "react";
import { JSONUIProvider, Renderer } from "@json-render/react";
import type { Spec } from "@json-render/react";

import { registry } from "../registry";
import { ProgressChecklist } from "./ProgressChecklist";
import type { ProgressSteps, SpecWithState, Turn } from "../types";

// The scrollable transcript: settled turns, then the in-progress turn while streaming.
// Rendering of each turn's dashboard is delegated to TurnView (unchanged behaviour).
export function MessageList({
  turns,
  streaming,
}: {
  turns: Turn[];
  streaming: { prompt: string; spec: Spec | null } | null;
}) {
  if (turns.length === 0 && !streaming) {
    return (
      <div className="message-list">
        <div className="message-list__empty">
          <h2>What would you like to know?</h2>
          <p>Ask a question about your data to build a dashboard.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
      <div className="message-list__inner">
        {turns.map((turn, index) => (
          <TurnView key={index} prompt={turn.prompt} spec={turn.spec} loading={false} />
        ))}
        {/* The in-progress turn renders below the settled transcript until it completes,
            at which point the parent moves it into `turns`. Its live checklist shows what
            the graph/LLM is doing; settled turns drop it (the dashboard stands on its own). */}
        {streaming && (
          <TurnView
            prompt={streaming.prompt}
            spec={streaming.spec}
            loading
            progress={(streaming.spec as SpecWithState | null)?.state?.progress}
          />
        )}
      </div>
    </div>
  );
}

// One turn's dashboard. Each turn gets its OWN JSONUIProvider because widget $state
// bindings are scoped per spec — sharing one store across turns would cross-bind data.
function TurnView({
  prompt,
  spec,
  loading,
  progress,
}: {
  prompt: string;
  spec: Spec | null;
  loading: boolean;
  progress?: ProgressSteps;
}) {
  // A fresh object per spec ref (one per patch) so JSONUIProvider re-flattens the
  // streamed state into its store, resolving $state as each widget's data arrives.
  const stateModel = useMemo(() => {
    const state = (spec as SpecWithState | null)?.state;
    return state ? { ...state } : {};
  }, [spec]);

  return (
    <section>
      <p className="turn__prompt">{prompt}</p>
      <ProgressChecklist steps={progress} />
      <JSONUIProvider registry={registry} initialState={stateModel}>
        {/* loading lets the renderer show partial trees gracefully while patches arrive */}
        <Renderer spec={spec} registry={registry} loading={loading} />
      </JSONUIProvider>
    </section>
  );
}
