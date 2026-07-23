import type { ReactNode } from "react";
import { act, cleanup, renderHook } from "@testing-library/react";
import { JSONUIProvider } from "@json-render/react";
import { afterEach, describe, expect, test } from "vitest";

import { registry } from "../registry";
import { useCrossFilter } from "./useCrossFilter";

afterEach(cleanup);

// The hook only works inside a provider (that is the per-dashboard state store it reads/writes).
function wrapper({ children }: { children: ReactNode }) {
  return (
    <JSONUIProvider registry={registry} initialState={{}}>
      {children}
    </JSONUIProvider>
  );
}

describe("useCrossFilter", () => {
  test("starts with no active filters", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    expect(result.current.filters).toEqual({});
    expect(result.current.activeCount).toBe(0);
  });

  test("select sets a field's value, and reading back reflects the write", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.select("category", "Books"));
    expect(result.current.filters).toEqual({ category: "Books" });
    expect(result.current.valueOf("category")).toBe("Books");
  });

  test("multiple fields compose (AND) and both stay active", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.select("category", "Books"));
    act(() => result.current.select("region", "West"));
    expect(result.current.filters).toEqual({ category: "Books", region: "West" });
    expect(result.current.activeCount).toBe(2);
  });

  test("toggle sets a field, and toggling the same value clears just that field", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.select("region", "West"));
    act(() => result.current.toggle("category", "Books"));
    act(() => result.current.toggle("category", "Books"));
    expect(result.current.filters).toEqual({ region: "West" });
  });

  test("clearField removes one field, clearAll removes everything", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.select("category", "Books"));
    act(() => result.current.select("region", "West"));
    act(() => result.current.clearField("category"));
    expect(result.current.filters).toEqual({ region: "West" });
    act(() => result.current.clearAll());
    expect(result.current.filters).toEqual({});
  });
});
