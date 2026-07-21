/** Human-readable copy for the errors the chat/edit streams can surface. */

/**
 * Turn a low-level failure into guidance a user can act on. A network failure reaches the UI
 * as the browser's bare "Failed to fetch"; server-sent messages are already meaningful and
 * pass through unchanged.
 *
 * @example
 *   friendlyError("Failed to fetch") // "Couldn't reach the server. Check your connection…"
 *   friendlyError("Query timed out") // "Query timed out"
 */
export function friendlyError(message: string): string {
  if (/failed to fetch|networkerror|load failed/i.test(message)) {
    return "Couldn't reach the server. Check your connection and try again.";
  }
  return message;
}
