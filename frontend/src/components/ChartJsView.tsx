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
  /** Called with a mark's index when the user selects it (drives cross-filtering). */
  onSelect?: (index: number) => void;
  /** The index of the mark to emphasise (others dim) when a selection targets this chart. */
  activeIndex?: number | null;
}

/** Render a Chart.js chart into a canvas, updating it in place as its data changes. */
export function ChartJsView({ kind, title, labels, datasets, onSelect, activeIndex }: ChartJsProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);
  // The latest render inputs, so the theme-change listener can repaint without
  // being re-subscribed on every data patch — and so Chart.js' onClick reads the
  // current onSelect, not the one captured when the chart was constructed.
  const inputsRef = useRef({ kind, labels, datasets, onSelect, activeIndex });
  inputsRef.current = { kind, labels, datasets, onSelect, activeIndex };

  // Apply current data + fresh theme tokens to the live chart. Shared by the data
  // effect and the OS-theme listener so both go through one update(), never a rebuild.
  const paint = useCallback(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const { kind, labels, datasets, activeIndex } = inputsRef.current;
    const tokens = readChartTokens();
    chart.data.labels = labels;
    chart.data.datasets = datasets.map((d, i) => styleDataset(d, i, kind, tokens, activeIndex));
    const options = baseOptions(kind, hasLegend(kind, datasets.length), tokens) as Chart["options"];
    // Route a canvas click through the latest onSelect: Chart.js hands us the active elements,
    // and the first is the clicked mark — a click on empty space passes none, selecting nothing.
    options.onClick = (_event, elements) => {
      const clicked = elements[0];
      if (clicked) inputsRef.current.onSelect?.(clicked.index);
    };
    chart.options = options;
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
  }, [paint, kind, labels, datasets, activeIndex]);

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
        {/* A pointer cursor signals the bars are clickable when the chart is a filter source
            (mouse affordance; the keyboard path is the revealed data-table controls below). */}
        <canvas
          ref={canvasRef}
          role="img"
          aria-label={describeChart(kind, title, labels, datasets)}
          style={onSelect ? { cursor: "pointer" } : undefined}
        />
      </div>
      <ChartDataTable
        title={title}
        kind={kind}
        labels={labels}
        datasets={datasets}
        onSelect={onSelect}
        activeIndex={activeIndex}
      />
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
//
// It also carries the chart's KEYBOARD cross-filter path: a canvas click is mouse-only, so
// when the chart is a filter source each category row-header is a real <button> that selects
// that mark (SC 2.1.1). The table reveals itself on :focus-within (see chart CSS) so the
// focused control is visible, not a hidden keyboard trap.
function ChartDataTable({
  title,
  kind,
  labels,
  datasets,
  onSelect,
  activeIndex,
}: {
  title: string;
  kind: string;
  labels: string[];
  datasets: ChartDataset[];
  onSelect?: (index: number) => void;
  activeIndex?: number | null;
}) {
  return (
    <table className="sr-only chart-data-table">
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
            <th scope="row">
              <CategoryHeader label={label} row={row} onSelect={onSelect} active={activeIndex === row} />
            </th>
            {datasets.map((dataset) => (
              <td key={dataset.label}>{dataset.data[row] ?? "—"}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// A category label: a plain string when the chart isn't a filter source, or a toggle button
// that selects this mark when it is. `aria-pressed` carries the active selection.
function CategoryHeader({
  label,
  row,
  onSelect,
  active,
}: {
  label: string;
  row: number;
  onSelect?: (index: number) => void;
  active: boolean;
}) {
  if (!onSelect) return <>{label}</>;
  return (
    <button type="button" className="chart-data-table__select" aria-pressed={active} onClick={() => onSelect(row)}>
      {label}
    </button>
  );
}

// A legend earns its place only when color must be decoded: ≥2 series, or a pie whose
// slices are the categories. A single series is named by the title — no legend box.
function hasLegend(kind: string, seriesCount: number): boolean {
  return kind === "pie" || seriesCount > 1;
}

// Suffixed onto an 8-digit hex to recede an unselected mark — the selected mark keeps its
// full-opacity hue, so a cross-filter selection reads as emphasis, not a colour change.
const DIM_ALPHA = "40";

// Dim every mark except the active one when a selection targets this chart's dimension; with
// no active index, colours pass through unchanged. `color` is one hue applied per category
// index (bars/points share a series hue; a pie already colours per slice).
function emphasize(color: string, data: unknown[], activeIndex: number | null | undefined): string | string[] {
  if (activeIndex === null || activeIndex === undefined) return color;
  return data.map((_, i) => (i === activeIndex ? color : `${color}${DIM_ALPHA}`));
}

/**
 * Colour + mark spec for one dataset. A single series wears the accent hue (not a
 * rainbow); multiple series take the ordered categorical palette by index (fixed
 * order, never a per-value rainbow). Marks are thin with rounded, zero-anchored ends.
 * When ``activeIndex`` is set the selected mark keeps its hue and the rest recede.
 */
function styleDataset(
  dataset: ChartDataset,
  index: number,
  kind: string,
  tokens: ChartTokens,
  activeIndex?: number | null,
) {
  const { categorical, accent, surface } = tokens;
  const seriesColor = index === 0 && kind !== "pie" ? accent : categorical[index % categorical.length];
  const base = { label: dataset.label, data: dataset.data };

  if (kind === "pie") {
    // Parts of a whole: colour per slice, a 2px surface-gap between slices.
    const slices = dataset.data.map((_, i) => categorical[i % categorical.length]);
    const colored = activeIndex === null || activeIndex === undefined
      ? slices
      : slices.map((hex, i) => (i === activeIndex ? hex : `${hex}${DIM_ALPHA}`));
    return { ...base, backgroundColor: colored, borderColor: surface, borderWidth: 2 };
  }
  if (kind === "line") {
    return { ...base, borderColor: seriesColor, backgroundColor: seriesColor, borderWidth: 2, pointRadius: 2, tension: 0 };
  }
  // bar: thin, capped, 4px rounded data-end growing from the baseline.
  const fill = emphasize(seriesColor, dataset.data, activeIndex);
  return { ...base, backgroundColor: fill, borderColor: fill, borderRadius: 4, borderSkipped: false, maxBarThickness: 24 };
}
