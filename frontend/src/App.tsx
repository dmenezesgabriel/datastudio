import { useMemo, useState } from "react";
import { JSONUIProvider, Renderer, useUIStream } from "@json-render/react";
import type { Spec } from "@json-render/react";

import { registry } from "./registry";
import { CONVERSATION_ID } from "./session";

// The stream carries both /elements patches (the LLM-authored widgets) and /state
// patches (each widget's rows, authored by the backend). useUIStream applies both,
// so spec.state holds the data the widgets' $state bindings resolve against.
type SpecWithState = Spec & { state?: Record<string, unknown> };

export function App() {
  const [question, setQuestion] = useState("");
  const { spec, isStreaming, error, send } = useUIStream({ api: "/api/chat" });

  // A fresh object per spec ref (one per patch) so JSONUIProvider re-flattens the
  // streamed state into its store, resolving $state as each widget's data arrives.
  const stateModel = useMemo(() => {
    const state = (spec as SpecWithState | null)?.state;
    return state ? { ...state } : {};
  }, [spec]);

  function ask() {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) return;
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
      <div style={{ marginTop: 24 }}>
        <JSONUIProvider registry={registry} initialState={stateModel}>
          {/* loading lets the renderer show partial trees gracefully while patches arrive */}
          <Renderer spec={spec} registry={registry} loading={isStreaming} />
        </JSONUIProvider>
      </div>
    </main>
  );
}

const mainStyle = {
  maxWidth: 720,
  margin: "40px auto",
  padding: "0 16px",
  fontFamily: "system-ui, sans-serif",
} as const;
