import { useMemo, useRef, useState } from "react";
import { useUIStream } from "@json-render/react";

import { Sidebar } from "./components/Sidebar";
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { useConversations } from "./hooks/useConversations";
import { newConversationId } from "./session";
import type { SpecWithState, ThreadSummary, Turn } from "./types";

// Transcripts are cached client-side per conversation id so switching threads is instant;
// the sidebar list and each reopened transcript come from the server (which owns the
// short-term memory keyed by the same id). "New chat" mints a fresh id.
export function App() {
  const firstId = useMemo(() => newConversationId(), []);
  const [activeId, setActiveId] = useState(firstId);
  const [turnsByConv, setTurnsByConv] = useState<Record<string, Turn[]>>({
    [firstId]: [],
  });
  const [question, setQuestion] = useState("");
  const { threads, refresh, loadTurns } = useConversations();

  // Refs so useUIStream's onComplete (bound once) records against the live thread/prompt.
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const livePrompt = useRef("");

  const { spec, isStreaming, error, send } = useUIStream({
    api: "/api/chat",
    onComplete: (finished) => {
      const id = activeIdRef.current;
      setTurnsByConv((prev) => ({
        ...prev,
        [id]: [
          ...(prev[id] ?? []),
          { prompt: livePrompt.current, spec: finished as SpecWithState },
        ],
      }));
      void refresh(); // the completed turn is now persisted server-side → update the sidebar
    },
  });

  function ask() {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) return;
    livePrompt.current = trimmed;
    setQuestion("");
    void send(trimmed, { conversation_id: activeId });
  }

  function newChat() {
    if (isStreaming) return;
    const id = newConversationId();
    setTurnsByConv((prev) => ({ ...prev, [id]: [] }));
    setActiveId(id);
  }

  async function selectThread(id: string) {
    if (isStreaming || id === activeId) return;
    setActiveId(id);
    if (turnsByConv[id]) return; // already cached this session
    const loaded = await loadTurns(id);
    setTurnsByConv((prev) => ({ ...prev, [id]: prev[id] ?? loaded }));
  }

  const activeTurns = turnsByConv[activeId] ?? [];
  const threadList = mergeActiveThread(threads, activeId, activeTurns);

  return (
    <div className="app-shell">
      <Sidebar
        threads={threadList}
        activeId={activeId}
        onNewChat={newChat}
        onSelect={selectThread}
      />
      <main className="main">
        <MessageList
          turns={activeTurns}
          streaming={isStreaming ? { prompt: livePrompt.current, spec } : null}
        />
        {error && (
          <p className="error-banner max-w-content mx-auto mb-4 text-base">
            {error.message}
          </p>
        )}
        <Composer
          value={question}
          onChange={setQuestion}
          onSubmit={ask}
          disabled={isStreaming}
        />
      </main>
    </div>
  );
}

// The active conversation may be brand-new (not yet saved server-side), so it won't be in
// the fetched list. Surface it at the top so the current thread is always visible/selected.
function mergeActiveThread(
  threads: ThreadSummary[],
  activeId: string,
  activeTurns: Turn[],
): ThreadSummary[] {
  if (threads.some((thread) => thread.id === activeId)) return threads;
  const title = activeTurns[0]?.prompt ?? "New chat";
  return [{ id: activeId, title }, ...threads];
}
