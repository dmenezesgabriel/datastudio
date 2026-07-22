import { useCallback, useRef, useState } from "react";
import { useUIStream } from "@json-render/react";
import type { Spec } from "@json-render/react";

import { useConversations } from "./useConversations";
import { newConversationId } from "../session";
import type { LoadState, SpecWithState, ThreadSummary, Turn } from "../types";

type Transcripts = Record<string, LoadState<Turn[]>>;

/** The chat state shared by every route: transcripts, the sidebar list, and one live stream. */
export type ChatSession = {
  /** Loaded transcripts by conversation id. A conversation absent here has not been opened. */
  transcripts: Transcripts;
  /** Sidebar summaries, refreshed whenever a turn is persisted. */
  threads: ThreadSummary[];
  /** Ensure a conversation's transcript is loaded; a no-op once it has an entry. */
  open: (conversationId: string) => void;
  /** Re-request a transcript unconditionally — what a failed load's retry calls. */
  reload: (conversationId: string) => void;
  /** Send a question, minting a conversation id when there is none. Returns the id used. */
  ask: (conversationId: string | null, prompt: string) => string;
  /** The conversation the live (or last) stream belongs to; null before the first send. */
  streamOwnerId: string | null;
  isStreaming: boolean;
  /** The question being answered right now, echoed above the streaming dashboard. */
  streamingPrompt: string;
  streamingSpec: Spec | null;
  /** The last stream's failure, owned by `streamOwnerId`'s conversation. */
  error: Error | null;
};

/**
 * Owns chat state above the router so a stream survives navigation.
 *
 * The URL — not this hook — decides which conversation is on screen, so every operation
 * takes the conversation id explicitly and a finished turn is filed against the thread
 * that asked it, even if the user has since navigated elsewhere.
 *
 * Example:
 *     const session = useChatSession();
 *     const id = session.ask(null, "Revenue by month");
 *     navigate(chatPath(id), { replace: true });
 */
export function useChatSession(): ChatSession {
  const [transcripts, setTranscripts] = useState<Transcripts>({});
  const [streamOwnerId, setStreamOwnerId] = useState<string | null>(null);
  const { threads, refresh, loadTurns } = useConversations();

  // The turn in flight, captured at send time. Reading the on-screen conversation in
  // `onComplete` instead would file the answer under whatever thread the user navigated
  // to while it streamed.
  const pending = useRef<{ conversationId: string; prompt: string }>({
    conversationId: "",
    prompt: "",
  });

  const { spec, isStreaming, error, send } = useUIStream({
    api: "/api/chat",
    onComplete: (finished) => {
      const { conversationId, prompt } = pending.current;
      appendTurn(setTranscripts, conversationId, {
        prompt,
        spec: finished as SpecWithState,
      });
      void refresh(); // the turn is now persisted server-side → update the sidebar
    },
  });

  // Conversations we have already taken responsibility for — fetched, or seeded by `ask`.
  // A ref, not derived from `transcripts`, so the "should I fetch?" decision stays outside
  // the state updater: React may invoke an updater twice, which would double the request.
  const requested = useRef<Set<string>>(new Set());

  const reload = useCallback(
    (conversationId: string) => {
      requested.current.add(conversationId);
      setTranscripts((prev) => ({ ...prev, [conversationId]: { status: "loading" } }));
      void loadTurns(conversationId).then((settled) => {
        setTranscripts((prev) => ({ ...prev, [conversationId]: settled }));
      });
    },
    [loadTurns],
  );

  const open = useCallback(
    (conversationId: string) => {
      // Skipped once we hold (or are fetching) it: re-fetching would clobber a transcript
      // whose turns only exist client-side while the server is still writing them.
      if (requested.current.has(conversationId)) return;
      reload(conversationId);
    },
    [reload],
  );

  const ask = useCallback(
    (conversationId: string | null, prompt: string): string => {
      const id = conversationId ?? newConversationId();
      pending.current = { conversationId: id, prompt };
      setStreamOwnerId(id);
      // Seed a first-question thread as ready-and-empty so the route we are about to
      // navigate to does not fetch an id the server has not saved yet (it would 404).
      if (!requested.current.has(id)) {
        requested.current.add(id);
        setTranscripts((prev) => ({ ...prev, [id]: { status: "ready", value: [] } }));
      }
      void send(prompt, { conversation_id: id });
      return id;
    },
    [send],
  );

  return {
    transcripts,
    threads,
    open,
    reload,
    ask,
    streamOwnerId,
    isStreaming,
    streamingPrompt: pending.current.prompt,
    streamingSpec: spec,
    error,
  };
}

// Appends to whatever the conversation already holds. A conversation that was never loaded
// (or whose load failed) starts from the turn we just witnessed rather than staying broken.
function appendTurn(
  setTranscripts: React.Dispatch<React.SetStateAction<Transcripts>>,
  conversationId: string,
  turn: Turn,
): void {
  setTranscripts((prev) => {
    const current = prev[conversationId];
    const existing = current?.status === "ready" ? current.value : [];
    return { ...prev, [conversationId]: { status: "ready", value: [...existing, turn] } };
  });
}
