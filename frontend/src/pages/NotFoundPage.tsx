import { Link } from "react-router-dom";

import { NEW_CHAT_PATH } from "../routes";
import { PageNotice } from "../components/PageNotice";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

// The catch-all route. Now that every surface is addressable, a mistyped or stale URL is
// reachable — it has to say so and offer a way back rather than render an empty shell.
export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <main className="main">
      <PageNotice heading="Page not found">
        <p>That address doesn’t match anything here.</p>
        <Link className="text-base" to={NEW_CHAT_PATH}>
          Start a new chat
        </Link>
      </PageNotice>
    </main>
  );
}
