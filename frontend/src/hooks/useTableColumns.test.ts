import { afterEach, expect, test, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useTableColumns } from "./useTableColumns";

afterEach(() => vi.unstubAllGlobals());

// Stands in for the per-table columns endpoint, recording which tables were asked for.
class FakeColumnsEndpoint {
  readonly asked: string[] = [];

  constructor(private readonly columnsByTable: Record<string, string[]>) {}

  install() {
    vi.stubGlobal("fetch", (url: string) => {
      const table = decodeURIComponent(url.split("/")[4] ?? "");
      this.asked.push(table);
      const columns = this.columnsByTable[table];
      if (columns === undefined) {
        return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ table, columns: columns.map((name) => ({ name })) }),
      });
    });
  }
}

test("loads the named table's columns", async () => {
  new FakeColumnsEndpoint({ events: ["amount", "category"] }).install();

  const { result } = renderHook(() => useTableColumns("events"));

  await waitFor(() => expect(result.current).toEqual(["amount", "category"]));
});

test("asks for nothing until a table is being referred to", async () => {
  const endpoint = new FakeColumnsEndpoint({ events: ["amount"] });
  endpoint.install();

  const { result } = renderHook(() => useTableColumns(null));

  expect(result.current).toEqual([]);
  expect(endpoint.asked).toEqual([]);
});

test("remembers a table it has already described", async () => {
  // Typing past the dot re-renders on every keystroke; each one must not cost a request.
  const endpoint = new FakeColumnsEndpoint({ events: ["amount"] });
  endpoint.install();
  const { result, rerender } = renderHook(({ table }) => useTableColumns(table), {
    initialProps: { table: "events" as string | null },
  });
  await waitFor(() => expect(result.current).toEqual(["amount"]));

  rerender({ table: null });
  rerender({ table: "events" });

  await waitFor(() => expect(result.current).toEqual(["amount"]));
  expect(endpoint.asked).toEqual(["events"]);
});

test("keeps each table's columns apart", async () => {
  const endpoint = new FakeColumnsEndpoint({ events: ["amount"], customers: ["email"] });
  endpoint.install();
  const { result, rerender } = renderHook(({ table }) => useTableColumns(table), {
    initialProps: { table: "events" as string | null },
  });
  await waitFor(() => expect(result.current).toEqual(["amount"]));

  rerender({ table: "customers" });

  await waitFor(() => expect(result.current).toEqual(["email"]));
});

test("suggests nothing rather than breaking when the table cannot be described", async () => {
  new FakeColumnsEndpoint({}).install();

  const { result } = renderHook(() => useTableColumns("dropped_table"));

  await waitFor(() => expect(result.current).toEqual([]));
});

test("suggests nothing rather than breaking when the request throws", async () => {
  vi.stubGlobal("fetch", () => Promise.reject(new Error("offline")));

  const { result } = renderHook(() => useTableColumns("events"));

  await waitFor(() => expect(result.current).toEqual([]));
});
