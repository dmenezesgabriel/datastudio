import { useCallback, useMemo, useRef, useState } from "react";
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
  const { threads, refresh, loadTurns } = useConversations();

  // Refs so useUIStream's onComplete (bound once) records against the live thread/prompt.
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const livePrompt = useRef("");

  const { spec, isStreaming, error, send, clear } = useUIStream({
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

  // Stable identities so the memoized Composer/Sidebar don't re-render on every streaming
  // patch (App re-renders per patch as `spec` grows; these callbacks must not churn with it).
  const ask = useCallback(
    (prompt: string) => {
      if (isStreaming) return;
      livePrompt.current = prompt;
      void send(prompt, { conversation_id: activeId });
    },
    [isStreaming, send, activeId],
  );

  const newChat = useCallback(() => {
    if (isStreaming) return;
    clear(); // drop any error/spec left over from the previous thread's stream
    const id = newConversationId();
    setTurnsByConv((prev) => ({ ...prev, [id]: [] }));
    setActiveId(id);
  }, [isStreaming, clear]);

  const selectThread = useCallback(
    async (id: string) => {
      if (isStreaming) return;
      if (id === activeId && turnsByConv[id]) return; // already open and loaded — nothing to do
      clear(); // the error banner belongs to the thread that produced it, not the one we open
      setActiveId(id);
      if (turnsByConv[id]) return; // already cached this session
      const loaded = await loadTurns(id);
      // Only cache a successful load; a failed one (null) stays uncached so re-clicking retries.
      if (loaded) setTurnsByConv((prev) => ({ ...prev, [id]: prev[id] ?? loaded }));
    },
    [isStreaming, activeId, turnsByConv, clear, loadTurns],
  );

  const activeTurns = turnsByConv[activeId] ?? [];
  // Memoized so the array identity is stable across streaming patches — otherwise a fresh
  // list every render (mergeActiveThread prepends the unsaved active thread) defeats memo(Sidebar).
  const threadList = useMemo(
    () => mergeActiveThread(threads, activeId, activeTurns),
    [threads, activeId, activeTurns],
  );

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
          conversationId={activeId}
          turns={activeTurns}
          streaming={isStreaming ? { prompt: livePrompt.current, spec } : null}
        />
        {error && (
          <p className="error-banner max-w-content mx-auto mb-4 text-base">
            {error.message}
          </p>
        )}
        <Composer onSubmit={ask} disabled={isStreaming} />
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
