import { useCallback, useEffect, useState } from "react";

import type { Settled, SpecWithState, ThreadSummary, Turn } from "../types";

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

  // The outcome is a three-way answer, not `Turn[] | null`: a deep link to a conversation
  // the server 404s ("missing") is a dead end to explain, while a failed request ("error")
  // is worth retrying. Neither may be cached as an empty-but-valid transcript.
  const loadTurns = useCallback(async (conversationId: string): Promise<Settled<Turn[]>> => {
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`);
      if (response.status === 404) return { status: "missing" };
      if (!response.ok) return { status: "error" };
      const payload = (await response.json()) as DetailPayload;
      const turns = payload.turns.map((turn) => ({ prompt: turn.prompt, spec: turn.spec }));
      return { status: "ready", value: turns };
    } catch {
      return { status: "error" };
    }
  }, []);

  return { threads, refresh, loadTurns };
}
