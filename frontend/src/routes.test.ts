import { expect, test } from "vitest";
import { matchRoutes } from "react-router-dom";

import {
  ARTIFACTS_PATH,
  ARTIFACT_ROUTE,
  CHAT_ROUTE,
  NEW_CHAT_PATH,
  artifactPath,
  chatPath,
} from "./routes";

// The app's route table, mirrored here so the round-trips below exercise the real
// resolution order (a bare "/artifacts" must not be read as an artifact id).
const ROUTE_TABLE = [
  { path: NEW_CHAT_PATH },
  { path: CHAT_ROUTE },
  { path: ARTIFACTS_PATH },
  { path: ARTIFACT_ROUTE },
];

// `matchRoutes` — not the standalone `matchPath` — is what the router runs, and it is the
// only one that percent-decodes params the way `useParams` reports them.
function resolve(pathname: string): { path?: string; params: Record<string, string | undefined> } {
  const matches = matchRoutes(ROUTE_TABLE, pathname);
  const last = matches?.[matches.length - 1];
  return { path: last?.route.path, params: last?.params ?? {} };
}

// The builders and the <Route path> patterns must agree — a builder that emits a URL the
// router can't match is a deep link that breaks only in production. These round-trips are
// the contract between routes.ts and App's route table.
test("a built chat path resolves to the chat route and yields its conversation id back", () => {
  const id = "8f8b7ed3-95d0-43d4-9c95-6e3def0479fc";
  const { path, params } = resolve(chatPath(id));
  expect(path).toBe(CHAT_ROUTE);
  expect(params.conversationId).toBe(id);
});

test("a built artifact path resolves to the artifact route and yields its artifact id back", () => {
  const id = "dash-42";
  const { path, params } = resolve(artifactPath(id));
  expect(path).toBe(ARTIFACT_ROUTE);
  expect(params.artifactId).toBe(id);
});

test("ids with URL-significant characters survive the round trip", () => {
  // Ids come from the server; nothing guarantees they stay UUID-shaped forever. A raw
  // slash or space would silently build a path that matches a different route (or none).
  const id = "a b/c?d#e";
  const { path, params } = resolve(chatPath(id));
  expect(path).toBe(CHAT_ROUTE);
  expect(params.conversationId).toBe(id);
});

test("the artifacts gallery path does not collide with a single artifact's route", () => {
  // "/artifacts" must reach the gallery, not the viewer with an empty id.
  expect(resolve(ARTIFACTS_PATH).path).toBe(ARTIFACTS_PATH);
});

test("the new-chat path is the app root", () => {
  // A brand-new chat has no server-side id yet, so it lives at the root until first send.
  expect(NEW_CHAT_PATH).toBe("/");
  expect(resolve(NEW_CHAT_PATH).path).toBe(NEW_CHAT_PATH);
});
