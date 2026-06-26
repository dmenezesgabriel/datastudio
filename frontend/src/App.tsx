import { useState } from "react";
import { JSONUIProvider, Renderer } from "@json-render/react";
import type { Spec } from "@json-render/react";

import { registry } from "./registry";

interface ChatResponse {
  conversation_id: string;
  response: string;
  sql_query: string;
  view: Spec;
}

// One conversation per page load; follow-up questions accumulate server-side.
const CONVERSATION_ID = crypto.randomUUID();

export function App() {
  const [question, setQuestion] = useState("");
  const [view, setView] = useState<Spec | null>(null);
  const [sqlQuery, setSqlQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask() {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      const data = await postQuestion(question);
      setView(data.view);
      setSqlQuery(data.sql_query);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={mainStyle}>
      <h1 style={{ fontSize: 20 }}>datastudio</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
        style={{ display: "flex", gap: 8 }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your data…"
          style={{ flex: 1, padding: 8, fontSize: 14 }}
        />
        <button type="submit" disabled={loading} style={{ padding: "8px 16px" }}>
          {loading ? "…" : "Ask"}
        </button>
      </form>
      {error && <p style={{ color: "#c00" }}>{error}</p>}
      <div style={{ marginTop: 24 }}>
        <JSONUIProvider registry={registry}>
          <Renderer spec={view} registry={registry} />
        </JSONUIProvider>
      </div>
      {sqlQuery && (
        <details style={{ marginTop: 24 }}>
          <summary>SQL</summary>
          <pre style={preStyle}>{sqlQuery}</pre>
        </details>
      )}
    </main>
  );
}

async function postQuestion(question: string): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: CONVERSATION_ID, question }),
  });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return (await response.json()) as ChatResponse;
}

const mainStyle = {
  maxWidth: 720,
  margin: "40px auto",
  padding: "0 16px",
  fontFamily: "system-ui, sans-serif",
} as const;

const preStyle = { overflowX: "auto", background: "#f6f6f6", padding: 12 } as const;
