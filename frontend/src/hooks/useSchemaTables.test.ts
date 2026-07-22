import { afterEach, expect, test, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import { useSchemaTables } from "./useSchemaTables";

afterEach(() => vi.unstubAllGlobals());

// Stands in for the schema endpoint in each of the ways it can actually behave.
class FakeSchemaEndpoint {
  calls = 0;
  constructor(private readonly reply: () => Promise<unknown>) {}

  install() {
    vi.stubGlobal("fetch", () => {
      this.calls += 1;
      return this.reply();
    });
  }
}

function answering(body: unknown) {
  return new FakeSchemaEndpoint(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) }));
}

test("loads the dataset's table names", async () => {
  answering({ tables: ["events", "customers"] }).install();
  const { result } = renderHook(() => useSchemaTables());

  act(() => result.current.load());

  await waitFor(() => expect(result.current.tables).toEqual(["events", "customers"]));
});

test("asks the server once however often loading is requested", async () => {
  // The field prewarms on every focus; each one must not cost a round trip.
  const endpoint = answering({ tables: ["events"] });
  endpoint.install();
  const { result } = renderHook(() => useSchemaTables());

  act(() => {
    result.current.load();
    result.current.load();
    result.current.load();
  });

  await waitFor(() => expect(result.current.tables).toEqual(["events"]));
  expect(endpoint.calls).toBe(1);
});

test("suggests nothing rather than breaking when the API fails", async () => {
  // The composer has to keep working with the schema endpoint down — the user simply types
  // the name instead of picking it.
  new FakeSchemaEndpoint(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) })).install();
  const { result } = renderHook(() => useSchemaTables());

  act(() => result.current.load());

  await waitFor(() => expect(result.current.tables).toEqual([]));
});

test("suggests nothing rather than breaking when the request throws", async () => {
  new FakeSchemaEndpoint(() => Promise.reject(new Error("offline"))).install();
  const { result } = renderHook(() => useSchemaTables());

  act(() => result.current.load());

  await waitFor(() => expect(result.current.tables).toEqual([]));
});

test("ignores a response that is not a list of names", async () => {
  // A proxy or an error page can answer 200 with something else entirely.
  answering({ tables: "not-a-list" }).install();
  const { result } = renderHook(() => useSchemaTables());

  act(() => result.current.load());

  await waitFor(() => expect(result.current.tables).toEqual([]));
});

test("keeps only the entries that are actually names", async () => {
  answering({ tables: ["events", 42, null, "customers"] }).install();
  const { result } = renderHook(() => useSchemaTables());

  act(() => result.current.load());

  await waitFor(() => expect(result.current.tables).toEqual(["events", "customers"]));
});
