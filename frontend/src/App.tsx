import { useCallback, useMemo, useState } from "react";
import { Route, Routes, useMatch } from "react-router-dom";

import { Sidebar } from "./components/Sidebar";
import { ChatPage } from "./pages/ChatPage";
import { GalleryPage } from "./pages/GalleryPage";
import { ArtifactPage } from "./pages/ArtifactPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { useChatSession } from "./hooks/useChatSession";
import { ARTIFACTS_PATH, ARTIFACT_ROUTE, CHAT_ROUTE, NEW_CHAT_PATH } from "./routes";
import type { ThreadSummary, Turn } from "./types";

const NO_TURNS: Turn[] = []; // a stable identity, so memo(Sidebar) survives streaming patches

// The app shell: persistent navigation around a routed main surface. Chat state lives here,
// above <Routes>, so a streaming answer survives the user navigating to another thread —
// the pages below decide what to show for the URL they were mounted at.
//
// No Router here; main.tsx supplies BrowserRouter and tests supply MemoryRouter.
export function App() {
  const session = useChatSession();
  // The mobile nav drawer's open state. Desktop keeps the sidebar always visible (CSS), so
  // this only matters at narrow widths where the sidebar collapses to an off-canvas drawer.
  const [navOpen, setNavOpen] = useState(false);
  const closeNav = useCallback(() => setNavOpen(false), []);

  // The URL — not component state — says which conversation is open. `useMatch` works here
  // because App sits inside the Router but outside the routed elements.
  const chatMatch = useMatch(CHAT_ROUTE);
  const isNewChat = useMatch(NEW_CHAT_PATH) !== null;
  const conversationId = chatMatch?.params.conversationId ?? null;

  const openTranscript = conversationId ? session.transcripts[conversationId] : undefined;
  const openTurns = openTranscript?.status === "ready" ? openTranscript.value : NO_TURNS;
  // Memoized so the array identity is stable across streaming patches — otherwise a fresh
  // list every render (mergeOpenThread prepends the unsaved thread) defeats memo(Sidebar).
  const threadList = useMemo(
    () =>
      isNewChat || conversationId
        ? mergeOpenThread(session.threads, conversationId, openTurns)
        : session.threads,
    [session.threads, isNewChat, conversationId, openTurns],
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
      <Sidebar id="app-sidebar" threads={threadList} onNavigate={closeNav} />
      {navOpen && (
        <button
          type="button"
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={closeNav}
        />
      )}
      <Routes>
        <Route path={NEW_CHAT_PATH} element={<ChatPage session={session} />} />
        <Route path={CHAT_ROUTE} element={<ChatPage session={session} />} />
        <Route path={ARTIFACTS_PATH} element={<GalleryPage />} />
        <Route path={ARTIFACT_ROUTE} element={<ArtifactPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  );
}

// The open conversation may be brand-new — unsaved server-side, so absent from the fetched
// list, or at "/" with no id at all. Surface it at the top so the thread you are looking at
// is always visible and marked as current.
function mergeOpenThread(
  threads: ThreadSummary[],
  conversationId: string | null,
  openTurns: Turn[],
): ThreadSummary[] {
  if (conversationId && threads.some((thread) => thread.id === conversationId)) return threads;
  // "Untitled chat", not "New chat" — the latter is the toolbar action's name, and two
  // controls sharing one accessible name is ambiguous to assistive tech (a11y audit QW-9).
  const title = openTurns[0]?.prompt ?? "Untitled chat";
  // An empty id is the chat at "/" that has not been asked anything yet; Sidebar links it
  // to the root, since there is no conversation to address until the first question.
  return [{ id: conversationId ?? "", title }, ...threads];
}
