import { memo } from "react";

import type { ThreadSummary } from "../types";

// The left navigation: a "New chat" action above the list of conversations. Selecting a
// thread reopens it; the active thread is highlighted (recognition over recall).
//
// memo so the thread list doesn't re-render on every streaming patch — with stable
// threads/activeId/callbacks it only re-renders when the conversation list actually changes.
export const Sidebar = memo(function Sidebar({
  threads,
  activeId,
  onNewChat,
  onSelect,
}: {
  threads: ThreadSummary[];
  activeId: string;
  onNewChat: () => void;
  onSelect: (id: string) => void;
}) {
  return (
    <nav
      className="sidebar flex flex-col gap-3 p-4 bg-subtle overflow-y-auto"
      aria-label="Conversations"
    >
      {/* The app's top-level heading — the only h1, so the transcript's per-turn h2s nest
          under it and the document has a correct heading outline. */}
      <h1 className="m-0 px-2 py-1 text-lg font-semibold">datastudio</h1>
      <button
        type="button"
        className="sidebar__new-chat flex items-center gap-2 w-full p-3 text-base font-medium bg-raised border-strong rounded-md cursor-pointer"
        onClick={onNewChat}
      >
        <span aria-hidden="true">+</span> New chat
      </button>
      <div className="px-2 pt-2 text-sm text-muted uppercase">
        Conversations
      </div>
      {threads.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted">No conversations yet.</p>
      ) : (
        <ul className="flex flex-col gap-1 list-none m-0 p-0">
          {threads.map((thread) => (
            <li key={thread.id}>
              <button
                type="button"
                className={
                  "thread-list__item w-full text-left px-3 py-2 text-base rounded-sm cursor-pointer truncate" +
                  (thread.id === activeId ? " thread-list__item--active" : "")
                }
                onClick={() => onSelect(thread.id)}
                title={thread.title}
              >
                {thread.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
});
