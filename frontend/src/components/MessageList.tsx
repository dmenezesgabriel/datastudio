import { memo, useMemo } from "react";
import { JSONUIProvider, Renderer } from "@json-render/react";
import type { Spec } from "@json-render/react";

import { registry } from "../registry";
import { PageNotice } from "./PageNotice";
import { ProgressChecklist } from "./ProgressChecklist";
import type { ProgressSteps, SpecWithState, Turn } from "../types";

// The scrollable transcript: settled turns, then the in-progress turn while streaming.
// Rendering of each turn's dashboard is delegated to TurnView. Dashboards (and their
// widgets) are auto-saved as artifacts server-side, so there is no per-turn save action.
export function MessageList({
  conversationId,
  turns,
  streaming,
}: {
  conversationId: string;
  turns: Turn[];
  streaming: { prompt: string; spec: Spec | null } | null;
}) {
  if (turns.length === 0 && !streaming) {
    return (
      <PageNotice heading="What would you like to know?">
        <p>Ask a question about your data to build a dashboard.</p>
      </PageNotice>
    );
  }

  return (
    <div className="message-list flex-1 overflow-y-auto py-6 px-4">
      <div className="message-list__inner max-w-content mx-auto flex flex-col gap-6 min-w-0">
        {turns.map((turn, index) => (
          // Keyed by conversation so switching threads remounts each turn (and its per-turn
          // JSONUIProvider) instead of reusing a same-index instance across conversations.
          <TurnView
            key={`${conversationId}:${index}`}
            prompt={turn.prompt}
            spec={turn.spec}
            loading={false}
          />
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
//
// memo so a settled turn (stable props) doesn't re-render — and rebuild its charts —
// every time a *later* turn streams a patch into the parent.
const TurnView = memo(function TurnView({
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
      {/* The question is this turn's heading (labels the dashboard below it), not a paragraph. */}
      <h2 className="font-semibold text-lg mt-0 mb-3 ml-5 py-2 px-3 bg-subtle border rounded-md">
        {prompt}
      </h2>
      <ProgressChecklist steps={progress} />
      <JSONUIProvider registry={registry} initialState={stateModel}>
        {/* loading lets the renderer show partial trees gracefully while patches arrive */}
        <Renderer spec={spec} registry={registry} loading={loading} />
      </JSONUIProvider>
    </section>
  );
});
