import { useCallback, useEffect, useRef } from "react";
import { Chart, registerables, type ChartType } from "chart.js";

import { applyFontDefaults, baseOptions, readChartTokens, type ChartTokens } from "./chartTheme";

Chart.register(...registerables);
// Global font/ink defaults come from the design tokens, once (see chartTheme).
applyFontDefaults();

export interface ChartDataset {
  label: string;
  data: (number | null)[]; // null is a gap in the series (missing/non-numeric cell)
}

export interface ChartJsProps {
  kind: "bar" | "line" | "pie";
  title: string;
  labels: string[];
  datasets: ChartDataset[];
}

/** Render a Chart.js chart into a canvas, updating it in place as its data changes. */
export function ChartJsView({ kind, title, labels, datasets }: ChartJsProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);
  // The latest render inputs, so the theme-change listener can repaint without
  // being re-subscribed on every data patch.
  const inputsRef = useRef({ kind, labels, datasets });
  inputsRef.current = { kind, labels, datasets };

  // Apply current data + fresh theme tokens to the live chart. Shared by the data
  // effect and the OS-theme listener so both go through one update(), never a rebuild.
  const paint = useCallback(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const { kind, labels, datasets } = inputsRef.current;
    const tokens = readChartTokens();
    chart.data.labels = labels;
    chart.data.datasets = datasets.map((d, i) => styleDataset(d, i, kind, tokens));
    chart.options = baseOptions(kind, hasLegend(kind, datasets.length), tokens) as Chart["options"];
    chart.update();
  }, []);

  // Instantiate once per chart type. Chart.js can't switch `type` on a live instance,
  // so only a kind change (bar↔line↔pie) rebuilds; data changes update in place below —
  // no teardown, so streaming patches and unrelated re-renders don't reset it.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const chart = new Chart(canvas, {
      type: kind as ChartType,
      data: { labels: [], datasets: [] },
      // maintainAspectRatio:false so the chart fills its sized .chart-box in the dashboard
      // grid — with the default true, side-by-side canvases overflow their cell and overlap.
      options: baseOptions(kind, false, readChartTokens()) as Chart["options"],
    });
    chartRef.current = chart;
    return () => {
      chart.destroy();
      chartRef.current = null;
    };
  }, [kind]);

  useEffect(() => {
    paint();
  }, [paint, kind, labels, datasets]);

  // Re-theme live when the OS flips light↔dark. Guarded: jsdom (tests) has no
  // matchMedia. Repaints through update(), so the chart is never rebuilt.
  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    query.addEventListener("change", paint);
    return () => query.removeEventListener("change", paint);
  }, [paint]);

  // Title rides above the canvas as real HTML (token typography, selectable, muted)
  // rather than baked into the pixel canvas — the takeaway, not chartjunk.
  //
  // A bare <canvas> is invisible to screen readers, so the chart also carries a text
  // alternative (a11y audit SC 1.1.1): the canvas is a labelled role="img" (a concise
  // summary), and an off-screen data table holds every value as the real equivalent.
  return (
    <figure className="chart-figure">
      {title ? <figcaption className="chart-title">{title}</figcaption> : null}
      <div className="chart-box">
        <canvas ref={canvasRef} role="img" aria-label={describeChart(kind, title, labels, datasets)} />
      </div>
      <ChartDataTable title={title} kind={kind} labels={labels} datasets={datasets} />
    </figure>
  );
}

// A one-line description for the canvas' aria-label: the takeaway a sighted user reads from
// the title/shape, condensed to words. The numbers live in the table below, not here.
function describeChart(kind: string, title: string, labels: string[], datasets: ChartDataset[]): string {
  const count = labels.length;
  const parts = [
    title.trim(),
    `${kind} chart`,
    `${count} ${count === 1 ? "category" : "categories"}`,
    datasets.length > 1 ? `${datasets.length} series` : "",
  ];
  return parts.filter(Boolean).join(", ");
}

// The screen-reader equivalent of the plotted marks: an off-screen (.sr-only) table of the
// same labels and values the canvas draws. One column per series; a null point reads "—".
function ChartDataTable({
  title,
  kind,
  labels,
  datasets,
}: {
  title: string;
  kind: string;
  labels: string[];
  datasets: ChartDataset[];
}) {
  return (
    <table className="sr-only">
      <caption>{title || `${kind} chart`} — data table</caption>
      <thead>
        <tr>
          <th scope="col">Label</th>
          {datasets.map((dataset) => (
            <th scope="col" key={dataset.label}>
              {dataset.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {labels.map((label, row) => (
          <tr key={`${label}-${row}`}>
            <th scope="row">{label}</th>
            {datasets.map((dataset) => (
              <td key={dataset.label}>{dataset.data[row] ?? "—"}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// A legend earns its place only when color must be decoded: ≥2 series, or a pie whose
// slices are the categories. A single series is named by the title — no legend box.
function hasLegend(kind: string, seriesCount: number): boolean {
  return kind === "pie" || seriesCount > 1;
}

/**
 * Colour + mark spec for one dataset. A single series wears the accent hue (not a
 * rainbow); multiple series take the ordered categorical palette by index (fixed
 * order, never a per-value rainbow). Marks are thin with rounded, zero-anchored ends.
 */
function styleDataset(dataset: ChartDataset, index: number, kind: string, tokens: ChartTokens) {
  const { categorical, accent, surface } = tokens;
  const seriesColor = index === 0 && kind !== "pie" ? accent : categorical[index % categorical.length];
  const base = { label: dataset.label, data: dataset.data };

  if (kind === "pie") {
    // Parts of a whole: colour per slice, a 2px surface-gap between slices.
    return {
      ...base,
      backgroundColor: dataset.data.map((_, i) => categorical[i % categorical.length]),
      borderColor: surface,
      borderWidth: 2,
    };
  }
  if (kind === "line") {
    return { ...base, borderColor: seriesColor, backgroundColor: seriesColor, borderWidth: 2, pointRadius: 2, tension: 0 };
  }
  // bar: thin, capped, 4px rounded data-end growing from the baseline.
  return { ...base, backgroundColor: seriesColor, borderColor: seriesColor, borderRadius: 4, borderSkipped: false, maxBarThickness: 24 };
}
