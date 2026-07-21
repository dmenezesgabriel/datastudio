import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

// Spies are hoisted so the vi.mock factory (itself hoisted above imports) can close over them.
const { constructed, updateSpy, destroySpy, instances } = vi.hoisted(() => ({
  constructed: vi.fn(),
  updateSpy: vi.fn(),
  destroySpy: vi.fn(),
  instances: [] as { data: { labels: unknown; datasets: DatasetStyle[] } }[],
}));

// The styled dataset shape ChartJsView writes onto the live chart (colour + label).
type DatasetStyle = { label: string; backgroundColor?: string; borderColor?: string };

// A fake Chart so the test runs without a real canvas 2D context (absent in jsdom) and can
// count how often the chart is (re)constructed vs. merely updated, and inspect the styled
// datasets pushed onto the instance.
vi.mock("chart.js", () => {
  class FakeChart {
    static register = vi.fn();
    data: { labels: unknown; datasets: DatasetStyle[] } = { labels: [], datasets: [] };
    options: Record<string, unknown> = {};
    constructor(_canvas: unknown, config: unknown) {
      constructed(config);
      instances.push(this);
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
  instances.length = 0;
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

test("colours a single series with one accent hue, not a per-series rainbow", () => {
  render(<ChartJsView {...ONE_BAR} />);
  // The one dataset wears the accent colour on both fill and stroke — no rainbow.
  const [dataset] = instances[0].data.datasets;
  expect(dataset.backgroundColor).toBe(dataset.borderColor);
  expect(dataset.backgroundColor).toBeTruthy();
});

test("exposes the chart to assistive tech: a labelled image plus a data-table equivalent", () => {
  // A canvas is invisible to screen readers (SC 1.1.1). The chart must therefore expose a
  // concise labelled image AND a text-equivalent table carrying the actual values.
  render(
    <ChartJsView
      kind="bar"
      title="Revenue by month"
      labels={["Jan", "Feb"]}
      datasets={[{ label: "revenue", data: [100, 250] }]}
    />,
  );

  // The canvas is a labelled img, not a blank to assistive tech.
  expect(screen.getByRole("img", { name: /Revenue by month/i })).toBeTruthy();

  // The equivalent data table carries every label and value.
  const table = within(screen.getByRole("table", { name: /Revenue by month/i }));
  expect(table.getByText("Jan")).toBeTruthy();
  expect(table.getByText("100")).toBeTruthy();
  expect(table.getByText("Feb")).toBeTruthy();
  expect(table.getByText("250")).toBeTruthy();
});

test("disables chart animation when the user prefers reduced motion", () => {
  // Chart.js animates by default; a user who asked for less motion must get a still chart.
  const original = window.matchMedia;
  window.matchMedia = ((query: string) =>
    ({
      matches: /reduce/.test(query),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      onchange: null,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as typeof window.matchMedia;

  render(<ChartJsView {...ONE_BAR} />);
  const config = constructed.mock.calls[0][0] as { options: { animation: unknown } };
  expect(config.options.animation).toBe(false);

  window.matchMedia = original;
});

test("gives two series two distinct categorical colours", () => {
  render(
    <ChartJsView
      kind="bar"
      title="Two"
      labels={["Jan"]}
      datasets={[
        { label: "a", data: [1] },
        { label: "b", data: [2] },
      ]}
    />,
  );
  const [first, second] = instances[0].data.datasets;
  expect(first.backgroundColor).toBeTruthy();
  expect(second.backgroundColor).toBeTruthy();
  expect(first.backgroundColor).not.toBe(second.backgroundColor);
});
