import { expect, test } from "vitest";

import { friendlyError } from "./errors";

test("rewrites a network failure into actionable guidance", () => {
  expect(friendlyError("Failed to fetch")).toMatch(/check your connection/i);
});

test("passes a server-sent message through unchanged", () => {
  expect(friendlyError("Query timed out")).toBe("Query timed out");
});
