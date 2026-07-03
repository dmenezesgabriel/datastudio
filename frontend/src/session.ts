// A conversation id keys the server-side short-term memory for a thread (sent in the
// /api/chat request context). "New chat" mints a fresh one; reopening a thread reuses
// its id, so follow-up questions accumulate against the right conversation.
export function newConversationId(): string {
  return crypto.randomUUID();
}
