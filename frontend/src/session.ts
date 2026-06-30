// One conversation per page load; follow-up questions accumulate server-side,
// keyed by this id (sent in the /api/chat request context).
export const CONVERSATION_ID = crypto.randomUUID();
