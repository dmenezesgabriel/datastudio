import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Composer } from "../components/Composer";
import { MessageList } from "../components/MessageList";
import { PageNotice } from "../components/PageNotice";
import { friendlyError } from "../errors";
import { NEW_CHAT_PATH, chatPath } from "../routes";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { ChatSession } from "../hooks/useChatSession";
import type { LoadState, Turn } from "../types";

// A conversation, addressed by URL. Mounted for both "/" (a chat with no id yet) and
// "/chat/:conversationId"; `useParams` is what tells the two apart. The session lives
// above the router, so a question keeps streaming even if the user navigates away —
// this page renders the stream only when it belongs to the conversation on screen.
export function ChatPage({ session }: { session: ChatSession }) {
  const { conversationId } = useParams<{ conversationId: string }>();
  const openedId = conversationId ?? null;
  const navigate = useNavigate();
  // Destructured rather than used through `session`: the session object is a fresh
  // identity on every streaming patch, and depending on it would give memo(Composer) a new
  // onSubmit per patch — exactly the re-render its memo exists to avoid.
  const { open, ask, isStreaming } = session;

  useEffect(() => {
    if (openedId) open(openedId);
  }, [openedId, open]);

  // A question asked at "/" mints the thread's id; the URL is corrected to it in place, so
  // Back leaves the app rather than returning to a blank copy of this same chat.
  const askHere = useCallback(
    (prompt: string) => {
      if (isStreaming) return; // one stream at a time — the composer is disabled too
      const id = ask(openedId, prompt);
      if (!openedId) navigate(chatPath(id), { replace: true });
    },
    [ask, isStreaming, openedId, navigate],
  );

  const load: LoadState<Turn[]> = openedId
    ? (session.transcripts[openedId] ?? { status: "loading" })
    : { status: "ready", value: [] };
  useDocumentTitle(threadTitle(session, openedId, load));

  // The live turn and any stream failure belong to the thread that asked, not to whichever
  // one is on screen — without this check they would follow the user across navigations.
  const ownsStream = session.streamOwnerId !== null && session.streamOwnerId === openedId;
  const failedSends = useFailedSendCount(ownsStream ? session.error : null);

  if (load.status === "missing") {
    return (
      <main className="main">
        <PageNotice heading="This conversation isn’t available">
          <p>It may have been removed, or it belongs to someone else.</p>
          <Link className="text-base" to={NEW_CHAT_PATH}>
            Start a new chat
          </Link>
        </PageNotice>
      </main>
    );
  }

  if (load.status === "error") {
    return (
      <main className="main">
        <PageNotice heading="Couldn’t load this conversation">
          <p>Something went wrong on the way to the server.</p>
          <button
            type="button"
            className="px-3 py-2 text-base border rounded-md cursor-pointer"
            onClick={() => openedId && session.reload(openedId)}
          >
            Try again
          </button>
        </PageNotice>
      </main>
    );
  }

  return (
    <main className="main">
      {load.status === "loading" ? (
        <PageNotice heading="Loading this conversation…" />
      ) : (
        <MessageList
          conversationId={openedId ?? "new"}
          turns={load.value}
          streaming={
            ownsStream && isStreaming
              ? { prompt: session.streamingPrompt, spec: session.streamingSpec }
              : null
          }
        />
      )}
      {ownsStream && session.error && (
        // role="alert" (an assertive live region) so screen readers announce the failure
        // the moment it appears — a mute <p> left AT users with no feedback (a11y SC 4.1.3).
        <p role="alert" className="error-banner max-w-content mx-auto mb-4 text-base">
          {friendlyError(session.error.message)}
        </p>
      )}
      <Composer
        onSubmit={askHere}
        disabled={isStreaming}
        restoreSignal={failedSends}
        autoFocus
      />
    </main>
  );
}

// The name for the tab and for browser history. URLs carry ids, so this is the only place
// a thread reads as itself: its first question, falling back to the sidebar's summary.
function threadTitle(
  session: ChatSession,
  conversationId: string | null,
  load: LoadState<Turn[]>,
): string | null {
  if (!conversationId) return "New chat";
  if (load.status === "ready" && load.value.length > 0) return load.value[0].prompt;
  return session.threads.find((thread) => thread.id === conversationId)?.title ?? null;
}

// Counts failed sends so the composer can restore the question it optimistically cleared on
// submit, letting a single retry re-send it (audit MOD-3).
function useFailedSendCount(error: Error | null): number {
  const [failedSends, setFailedSends] = useState(0);
  useEffect(() => {
    if (error) setFailedSends((count) => count + 1);
  }, [error]);
  return failedSends;
}
