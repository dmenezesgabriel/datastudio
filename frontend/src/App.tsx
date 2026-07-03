import { useMemo, useRef, useState } from "react";
import { JSONUIProvider, Renderer, useUIStream } from "@json-render/react";
import type { Spec } from "@json-render/react";

import { registry } from "./registry";
import { CONVERSATION_ID } from "./session";

// The stream carries both /elements patches (the LLM-authored widgets) and /state
// patches (each widget's rows, authored by the backend). useUIStream applies both,
// so spec.state holds the data the widgets' $state bindings resolve against.
type SpecWithState = Spec & { state?: Record<string, unknown> };

// One completed exchange in the transcript: the question the user asked and the
// dashboard the assistant produced for it.
type Turn = { prompt: string; spec: SpecWithState };

export function App() {
  const [question, setQuestion] = useState("");
  // The conversation transcript grows client-side; the backend keeps its own memory
  // keyed by CONVERSATION_ID. Each completed turn keeps its own finished spec because
  // useUIStream resets `spec` to empty on the next send (which would wipe it otherwise).
  const [turns, setTurns] = useState<Turn[]>([]);
  // Remembered when the send fires so onComplete can pair the answer with its question.
  const livePrompt = useRef("");
  const { spec, isStreaming, error, send } = useUIStream({
    api: "/api/chat",
    onComplete: (finished) =>
      setTurns((prev) => [...prev, { prompt: livePrompt.current, spec: finished as SpecWithState }]),
  });

  function ask() {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) return;
    livePrompt.current = trimmed;
    setQuestion("");
    void send(trimmed, { conversation_id: CONVERSATION_ID });
  }

  return (
    <main style={mainStyle}>
      <h1 style={{ fontSize: 20 }}>datastudio</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
        style={{ display: "flex", gap: 8 }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your data…"
          style={{ flex: 1, padding: 8, fontSize: 14 }}
        />
        <button type="submit" disabled={isStreaming} style={{ padding: "8px 16px" }}>
          {isStreaming ? "…" : "Ask"}
        </button>
      </form>
      {error && <p style={{ color: "#c00" }}>{error.message}</p>}
      <div style={transcriptStyle}>
        {turns.map((turn, index) => (
          <TurnView key={index} prompt={turn.prompt} spec={turn.spec} loading={false} />
        ))}
        {/* The in-progress turn renders below the settled transcript until it completes,
            at which point onComplete moves it into `turns`. */}
        {isStreaming && <TurnView prompt={livePrompt.current} spec={spec} loading />}
      </div>
    </main>
  );
}

// One turn's dashboard. Each turn gets its OWN JSONUIProvider because widget $state
// bindings are scoped per spec — sharing one store across turns would cross-bind data.
function TurnView({
  prompt,
  spec,
  loading,
}: {
  prompt: string;
  spec: Spec | null;
  loading: boolean;
}) {
  // A fresh object per spec ref (one per patch) so JSONUIProvider re-flattens the
  // streamed state into its store, resolving $state as each widget's data arrives.
  const stateModel = useMemo(() => {
    const state = (spec as SpecWithState | null)?.state;
    return state ? { ...state } : {};
  }, [spec]);

  return (
    <section>
      <p style={promptStyle}>{prompt}</p>
      <JSONUIProvider registry={registry} initialState={stateModel}>
        {/* loading lets the renderer show partial trees gracefully while patches arrive */}
        <Renderer spec={spec} registry={registry} loading={loading} />
      </JSONUIProvider>
    </section>
  );
}

const mainStyle = {
  maxWidth: 720,
  margin: "40px auto",
  padding: "0 16px",
  fontFamily: "system-ui, sans-serif",
} as const;

const transcriptStyle = {
  marginTop: 24,
  display: "flex",
  flexDirection: "column",
  gap: 32,
} as const;

const promptStyle = {
  margin: "0 0 12px",
  fontWeight: 600,
} as const;
