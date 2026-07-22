import { memo } from "react";
import { Link, NavLink } from "react-router-dom";

import { ARTIFACTS_PATH, NEW_CHAT_PATH, chatPath } from "../routes";
import type { ThreadSummary } from "../types";

// The left navigation: a "New chat" action above the list of conversations. Every entry is
// a NavLink rather than a button — each destination is an address, so it can be opened in
// a new tab or copied, and the browser marks the open one with aria-current="page"
// (recognition over recall, without hand-rolled active-state props).
//
// memo so the thread list doesn't re-render on every streaming patch — with stable
// threads/callbacks it only re-renders when the conversation list actually changes.
export const Sidebar = memo(function Sidebar({
  id,
  threads,
  onNavigate,
}: {
  // The nav's DOM id, so the mobile menu button can point at it via aria-controls.
  id?: string;
  threads: ThreadSummary[];
  // Called after any navigation choice so the parent can close the mobile drawer. A no-op
  // on desktop (the drawer isn't open there).
  onNavigate?: () => void;
}) {
  return (
    <nav
      id={id}
      className="sidebar flex flex-col gap-3 p-4 bg-subtle overflow-y-auto"
      aria-label="Conversations"
    >
      {/* The app's top-level heading — the only h1, so the transcript's per-turn h2s nest
          under it and the document has a correct heading outline. */}
      <h1 className="m-0 px-2 py-1 text-lg font-semibold">datastudio</h1>
      {/* A plain Link, not a NavLink: "New chat" is an action, and marking it as the
          current page at "/" would leave two entries claiming aria-current — the unsaved
          thread below already carries that (a11y audit QW-9). */}
      <Link
        className="sidebar__new-chat flex items-center gap-2 w-full p-3 text-base font-medium bg-raised border-strong rounded-md cursor-pointer"
        to={NEW_CHAT_PATH}
        onClick={onNavigate}
      >
        <span aria-hidden="true">+</span> New chat
      </Link>
      <NavLink
        className={({ isActive }) =>
          "sidebar__artifacts flex items-center gap-2 w-full p-3 text-base font-medium bg-raised border-strong rounded-md cursor-pointer" +
          (isActive ? " thread-list__item--active" : "")
        }
        to={ARTIFACTS_PATH}
        onClick={onNavigate}
      >
        <span aria-hidden="true">▤</span> Artifacts
      </NavLink>
      <div className="px-2 pt-2 text-sm text-muted uppercase">Conversations</div>
      {threads.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted">No conversations yet.</p>
      ) : (
        <ul className="flex flex-col gap-1 list-none m-0 p-0">
          {threads.map((thread) => (
            <li key={thread.id}>
              <ThreadLink thread={thread} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
});

// One conversation in the list. A thread with no id yet (the unsaved chat at "/") links to
// the root, so the entry stays selectable before its first question is answered.
function ThreadLink({ thread, onNavigate }: { thread: ThreadSummary; onNavigate?: () => void }) {
  return (
    <NavLink
      className={({ isActive }) =>
        "thread-list__item block w-full text-left px-3 py-2 text-base rounded-sm cursor-pointer truncate" +
        (isActive ? " thread-list__item--active" : "")
      }
      to={thread.id ? chatPath(thread.id) : NEW_CHAT_PATH}
      end
      title={thread.title}
      onClick={onNavigate}
    >
      {thread.title}
    </NavLink>
  );
}
