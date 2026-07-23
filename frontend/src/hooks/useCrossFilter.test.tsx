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

  test("toggle adds a value, and toggling it again removes just that value", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.toggle("category", "Books"));
    expect(result.current.filters).toEqual({ category: ["Books"] });
    expect(result.current.valuesOf("category")).toEqual(["Books"]);
    act(() => result.current.toggle("category", "Toys"));
    expect(result.current.filters).toEqual({ category: ["Books", "Toys"] });
    act(() => result.current.toggle("category", "Books"));
    expect(result.current.filters).toEqual({ category: ["Toys"] });
  });

  test("toggling away the last value drops the field key", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.toggle("category", "Books"));
    act(() => result.current.toggle("category", "Books"));
    expect(result.current.filters).toEqual({});
  });

  test("multiple fields compose (AND) and both stay active", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.toggle("category", "Books"));
    act(() => result.current.toggle("region", "West"));
    expect(result.current.filters).toEqual({ category: ["Books"], region: ["West"] });
    expect(result.current.activeCount).toBe(2);
  });

  test("setField replaces a field's whole value set, and an empty set drops the field", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.setField("category", ["Books", "Toys", "Games"]));
    expect(result.current.filters).toEqual({ category: ["Books", "Toys", "Games"] });
    act(() => result.current.setField("category", []));
    expect(result.current.filters).toEqual({});
  });

  test("clearField removes one field, clearAll removes everything", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.toggle("category", "Books"));
    act(() => result.current.toggle("region", "West"));
    act(() => result.current.clearField("category"));
    expect(result.current.filters).toEqual({ region: ["West"] });
    act(() => result.current.clearAll());
    expect(result.current.filters).toEqual({});
  });

  test("replace writes the reconciled set atomically", () => {
    const { result } = renderHook(() => useCrossFilter(), { wrapper });
    act(() => result.current.toggle("category", "Books"));
    act(() => result.current.replace({ region: ["West", "East"] }));
    expect(result.current.filters).toEqual({ region: ["West", "East"] });
  });
});
