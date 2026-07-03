import type { ThreadSummary } from "../types";

// The left navigation: a "New chat" action above the list of conversations. Selecting a
// thread reopens it; the active thread is highlighted (recognition over recall).
export function Sidebar({
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
    <nav className="sidebar" aria-label="Conversations">
      <div className="sidebar__brand">datastudio</div>
      <button type="button" className="sidebar__new-chat" onClick={onNewChat}>
        <span aria-hidden="true">+</span> New chat
      </button>
      <div className="sidebar__section-label">Conversations</div>
      {threads.length === 0 ? (
        <p className="thread-list__empty">No conversations yet.</p>
      ) : (
        <ul className="thread-list">
          {threads.map((thread) => (
            <li key={thread.id}>
              <button
                type="button"
                className={
                  "thread-list__item" +
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
}
