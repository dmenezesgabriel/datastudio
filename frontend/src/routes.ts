// The only module that knows the app's URL syntax. Components build links through these
// helpers and App declares its <Route path> from these patterns, so a path is never
// spelled out twice — the pair is round-tripped in routes.test.ts.

/** A brand-new chat, before its first question gives it a server-side id. */
export const NEW_CHAT_PATH = "/";

/** The gallery of saved dashboards. */
export const ARTIFACTS_PATH = "/artifacts";

/** `<Route path>` pattern for one conversation; its param is `conversationId`. */
export const CHAT_ROUTE = "/chat/:conversationId";

/** `<Route path>` pattern for one saved dashboard; its param is `artifactId`. */
export const ARTIFACT_ROUTE = "/artifacts/:artifactId";

/**
 * The URL of one conversation.
 *
 * Example:
 *     <Link to={chatPath(thread.id)}>{thread.title}</Link>
 */
export function chatPath(conversationId: string): string {
  return `/chat/${encodeURIComponent(conversationId)}`;
}

/**
 * The URL of one saved dashboard.
 *
 * Example:
 *     navigate(artifactPath(artifact.id));
 */
export function artifactPath(artifactId: string): string {
  return `${ARTIFACTS_PATH}/${encodeURIComponent(artifactId)}`;
}
