import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

// Spies are hoisted so the vi.mock factory (itself hoisted above imports) can close over them.
const { constructed, updateSpy, destroySpy } = vi.hoisted(() => ({
  constructed: vi.fn(),
  updateSpy: vi.fn(),
  destroySpy: vi.fn(),
}));

// A fake Chart so the test runs without a real canvas 2D context (absent in jsdom) and can
// count how often the chart is (re)constructed vs. merely updated.
vi.mock("chart.js", () => {
  class FakeChart {
    static register = vi.fn();
    data: { labels: unknown; datasets: unknown } = { labels: [], datasets: [] };
    options: Record<string, unknown> = {};
    constructor(_canvas: unknown, config: unknown) {
      constructed(config);
    }
    update = updateSpy;
    destroy = destroySpy;
  }
  return { Chart: FakeChart, registerables: [] };
});

import { ChartJsView, type ChartJsProps } from "./ChartJsView";

const ONE_BAR: ChartJsProps = { kind: "bar", title: "Revenue", labels: ["Jan"], datasets: [{ label: "rev", data: [1] }] };

afterEach(() => {
  cleanup();
  constructed.mockClear();
  updateSpy.mockClear();
  destroySpy.mockClear();
});

test("updates in place instead of tearing down when only prop identity changes", () => {
  // The registry hands ChartJsView brand-new labels/datasets arrays on every render. A
  // re-render (e.g. a streaming patch) must update the live chart, not destroy + rebuild it.
  const { rerender } = render(<ChartJsView {...ONE_BAR} />);
  expect(constructed).toHaveBeenCalledTimes(1);
  expect(updateSpy).toHaveBeenCalledTimes(1);

  rerender(<ChartJsView kind="bar" title="Revenue" labels={["Jan"]} datasets={[{ label: "rev", data: [1] }]} />);
  expect(constructed).toHaveBeenCalledTimes(1); // not rebuilt
  expect(destroySpy).not.toHaveBeenCalled();
  expect(updateSpy).toHaveBeenCalledTimes(2); // pushed through instead
});

test("rebuilds when the chart type changes — Chart.js can't swap type on a live instance", () => {
  const { rerender } = render(<ChartJsView {...ONE_BAR} />);
  expect(constructed).toHaveBeenCalledTimes(1);

  rerender(<ChartJsView {...ONE_BAR} kind="line" />);
  expect(destroySpy).toHaveBeenCalledTimes(1);
  expect(constructed).toHaveBeenCalledTimes(2);
});

test("destroys the chart on unmount", () => {
  const { unmount } = render(<ChartJsView {...ONE_BAR} />);
  unmount();
  expect(destroySpy).toHaveBeenCalledTimes(1);
});
