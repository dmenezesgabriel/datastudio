import { useEffect } from "react";

const APP_NAME = "Data Studio";

/**
 * Name the current page in the browser tab and in history.
 *
 * URLs carry plain ids rather than slugs, so the document title is what makes a tab or a
 * history entry recognisable. Pass null while the name is still unknown.
 *
 * Example:
 *     useDocumentTitle(thread?.title ?? null); // "Revenue by month · Data Studio"
 */
export function useDocumentTitle(title: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
  }, [title]);
}
