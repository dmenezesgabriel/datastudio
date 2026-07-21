import { useCallback, useMemo, useRef, useState } from "react";
import { useUIStream } from "@json-render/react";

import { Sidebar } from "./components/Sidebar";
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { ArtifactGallery } from "./components/ArtifactGallery";
import { ArtifactView } from "./components/ArtifactView";
import { useConversations } from "./hooks/useConversations";
import { useArtifacts } from "./hooks/useArtifacts";
import { newConversationId } from "./session";
import { friendlyError } from "./errors";
import type { SpecWithState, ThreadSummary, Turn } from "./types";

// Which surface the main pane shows. Chat is the default; the gallery lists saved
// dashboards and an "artifact" opens one for viewing/editing. No router — a saved
// dashboard is not deep-linkable in v1, so a small view state is enough.
type View = { kind: "chat" } | { kind: "gallery" } | { kind: "artifact"; id: string };

// Transcripts are cached client-side per conversation id so switching threads is instant;
// the sidebar list and each reopened transcript come from the server (which owns the
// short-term memory keyed by the same id). "New chat" mints a fresh id.
export function App() {
  const firstId = useMemo(() => newConversationId(), []);
  const [activeId, setActiveId] = useState(firstId);
  const [turnsByConv, setTurnsByConv] = useState<Record<string, Turn[]>>({
    [firstId]: [],
  });
  const [view, setView] = useState<View>({ kind: "chat" });
  // The mobile nav drawer's open state. Desktop keeps the sidebar always visible (CSS), so
  // this only matters at narrow widths where the sidebar collapses to an off-canvas drawer.
  const [navOpen, setNavOpen] = useState(false);
  const closeNav = useCallback(() => setNavOpen(false), []);
  // Bumped when a turn completes; the composer watches it to clear the draft only on success
  // (a failed send keeps the question to retry — audit MOD-3).
  const [completedTurns, setCompletedTurns] = useState(0);
  const { threads, refresh, loadTurns } = useConversations();
  const { artifacts, refresh: refreshArtifacts, deleteArtifact } = useArtifacts();

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
      void refreshArtifacts(); // the turn auto-saved its dashboard + widgets → refresh the gallery
      setCompletedTurns((n) => n + 1); // success → let the composer clear its draft
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
    setView({ kind: "chat" });
  }, [isStreaming, clear]);

  const selectThread = useCallback(
    async (id: string) => {
      if (isStreaming) return;
      setView({ kind: "chat" });
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

  const openArtifacts = useCallback(() => {
    if (isStreaming) return;
    void refreshArtifacts();
    setView({ kind: "gallery" });
  }, [isStreaming, refreshArtifacts]);

  const activeTurns = turnsByConv[activeId] ?? [];
  // Memoized so the array identity is stable across streaming patches — otherwise a fresh
  // list every render (mergeActiveThread prepends the unsaved active thread) defeats memo(Sidebar).
  const threadList = useMemo(
    () => mergeActiveThread(threads, activeId, activeTurns),
    [threads, activeId, activeTurns],
  );

  return (
    <div className={"app-shell" + (navOpen ? " app-shell--nav-open" : "")}>
      {/* Mobile-only top bar (hidden on desktop via CSS): the only route to the nav once the
          sidebar collapses to a drawer. Without it, narrow viewports lost New chat, Artifacts,
          and thread switching entirely. See a11y audit LG-1. */}
      <header className="mobile-bar">
        <button
          type="button"
          className="mobile-bar__menu"
          aria-controls="app-sidebar"
          aria-expanded={navOpen}
          aria-label={navOpen ? "Close navigation" : "Open navigation"}
          onClick={() => setNavOpen((open) => !open)}
        >
          <span aria-hidden="true">☰</span>
        </button>
        <span className="mobile-bar__wordmark">datastudio</span>
      </header>
      <Sidebar
        id="app-sidebar"
        threads={threadList}
        activeId={activeId}
        view={view.kind === "chat" ? "chat" : "artifacts"}
        onNewChat={newChat}
        onSelect={selectThread}
        onOpenArtifacts={openArtifacts}
        onNavigate={closeNav}
      />
      {navOpen && (
        <button
          type="button"
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={closeNav}
        />
      )}
      {view.kind === "chat" && (
        <main className="main">
          <MessageList
            conversationId={activeId}
            turns={activeTurns}
            streaming={isStreaming ? { prompt: livePrompt.current, spec } : null}
          />
          {error && (
            // role="alert" (an assertive live region) so screen readers announce the
            // failure the moment it appears — a mute <p> left AT users with no feedback
            // that their question failed. See a11y audit SC 4.1.3.
            <p role="alert" className="error-banner max-w-content mx-auto mb-4 text-base">
              {friendlyError(error.message)}
            </p>
          )}
          <Composer onSubmit={ask} disabled={isStreaming} clearSignal={completedTurns} autoFocus />
        </main>
      )}
      {view.kind === "gallery" && (
        <main className="main">
          <ArtifactGallery
            artifacts={artifacts}
            onOpen={(id) => setView({ kind: "artifact", id })}
            onDelete={(id) => void deleteArtifact(id)}
          />
        </main>
      )}
      {view.kind === "artifact" && (
        <ArtifactView
          key={view.id}
          artifactId={view.id}
          onBack={() => setView({ kind: "gallery" })}
        />
      )}
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
  // "Untitled chat", not "New chat" — the latter is the toolbar action's name, and two
  // controls sharing one accessible name is ambiguous to assistive tech (a11y audit QW-9).
  const title = activeTurns[0]?.prompt ?? "Untitled chat";
  return [{ id: activeId, title }, ...threads];
}
