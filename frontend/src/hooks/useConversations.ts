import { useCallback, useEffect, useState } from "react";

import type { SpecWithState, ThreadSummary, Turn } from "../types";

type ListPayload = { conversations: { conversation_id: string; title: string }[] };
type DetailPayload = { turns: { prompt: string; spec: SpecWithState }[] };

// Read-side conversation state for the sidebar: the list of past threads and a loader
// for one thread's transcript. Writes happen through the chat stream; this hook only
// reads, and is best-effort — a failed fetch leaves the sidebar unchanged rather than
// breaking the chat.
export function useConversations() {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/conversations");
      if (!response.ok) return;
      const payload = (await response.json()) as ListPayload;
      setThreads(payload.conversations.map((c) => ({ id: c.conversation_id, title: c.title })));
    } catch {
      // Sidebar is non-critical chrome; ignore transient network errors.
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // null signals a failed load (vs. an empty-but-valid transcript `[]`), so the caller can
  // avoid caching a transient failure as "this conversation is empty" and retry next time.
  const loadTurns = useCallback(async (conversationId: string): Promise<Turn[] | null> => {
    try {
      const response = await fetch(`/api/conversations/${conversationId}`);
      if (!response.ok) return null;
      const payload = (await response.json()) as DetailPayload;
      return payload.turns.map((turn) => ({ prompt: turn.prompt, spec: turn.spec }));
    } catch {
      return null;
    }
  }, []);

  return { threads, refresh, loadTurns };
}
