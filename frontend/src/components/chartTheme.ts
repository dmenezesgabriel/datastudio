/**
 * The one place Chart.js is themed. Charts render onto a canvas, which can't read
 * CSS variables, so we read the design tokens once (getComputedStyle) and hand
 * Chart.js a decluttered option set: no axis frame, hairline horizontal gridlines,
 * muted token ink, the app sans, styled tooltips. Kept behind this thin module so
 * ChartJsView never reaches into Chart.js globals or hardcodes a hex.
 */
import { Chart } from "chart.js";

/** The token values a chart needs, resolved to concrete hex/strings for the canvas. */
export interface ChartTokens {
  categorical: string[]; // --chart-1..8, in fixed CVD-safe order
  accent: string; // --chart-accent (single-series hue)
  grid: string;
  axis: string;
  surface: string;
  tooltipBorder: string;
  fontFamily: string;
}

// jsdom (tests) and a canvas with no stylesheet return "" for a custom property, so
// every token carries the light-mode default from tokens.css as a fallback.
const FALLBACK: ChartTokens = {
  categorical: ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"],
  accent: "#2a78d6",
  grid: "#e1e0d9",
  axis: "#6b6d75",
  surface: "#ffffff",
  tooltipBorder: "#e3e3e6",
  fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
};

function cssVar(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  const value = styles.getPropertyValue(name).trim();
  return value === "" ? fallback : value;
}

/** Read the live chart tokens off :root — recomputed on theme change so charts re-theme. */
export function readChartTokens(): ChartTokens {
  if (typeof window === "undefined" || !window.getComputedStyle) return FALLBACK;
  const s = window.getComputedStyle(document.documentElement);
  return {
    categorical: FALLBACK.categorical.map((hex, i) => cssVar(s, `--chart-${i + 1}`, hex)),
    accent: cssVar(s, "--chart-accent", FALLBACK.accent),
    grid: cssVar(s, "--chart-grid", FALLBACK.grid),
    axis: cssVar(s, "--chart-axis", FALLBACK.axis),
    surface: cssVar(s, "--chart-surface", FALLBACK.surface),
    tooltipBorder: cssVar(s, "--chart-tooltip-border", FALLBACK.tooltipBorder),
    fontFamily: cssVar(s, "--font-sans", FALLBACK.fontFamily),
  };
}

/** Set Chart.js' global font + default ink to the app's tokens, once at module load. */
export function applyFontDefaults(): void {
  if (!Chart.defaults?.font) return; // a stubbed Chart (tests) has no defaults to set
  const tokens = readChartTokens();
  Chart.defaults.font.family = tokens.fontFamily;
  Chart.defaults.color = tokens.axis;
}

// bar/line carry an x/y frame we want to strip; pie has no cartesian scales.
const CARTESIAN = new Set(["bar", "line"]);

// Whether the OS/browser is set to reduce motion. Guarded for jsdom (no matchMedia).
function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * The decluttered option set for a chart: recessive grid/axes, one legend only when
 * it earns its place (≥2 series, or a pie's slice identity), a tooltip styled to the
 * token surface. Title is rendered in HTML by ChartJsView, so it's disabled here.
 */
export function baseOptions(kind: string, hasLegend: boolean, tokens: ChartTokens) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    // Honour a reduced-motion preference: a still chart for users who asked for less motion
    // (a11y audit SC 2.3.3). Recomputed on every paint(), so it also covers live updates.
    animation: prefersReducedMotion() ? false : undefined,
    scales: CARTESIAN.has(kind) ? cartesianScales(kind, tokens) : undefined,
    plugins: {
      title: { display: false },
      legend: legendConfig(hasLegend, tokens),
      tooltip: tooltipConfig(tokens),
    },
  };
}

// Horizontal hairline gridlines only, no vertical grid, no axis frame; bars start at
// zero (bar length is the encoding — a truncated baseline lies). Line y may float.
function cartesianScales(kind: string, tokens: ChartTokens) {
  return {
    x: {
      grid: { display: false },
      border: { display: false },
      ticks: { color: tokens.axis },
    },
    y: {
      beginAtZero: kind === "bar",
      grid: { color: tokens.grid, drawTicks: false },
      border: { display: false },
      ticks: { color: tokens.axis },
    },
  };
}

function legendConfig(hasLegend: boolean, tokens: ChartTokens) {
  return {
    display: hasLegend,
    position: "top" as const,
    labels: { color: tokens.axis, usePointStyle: true, boxWidth: 8, boxHeight: 8 },
  };
}

// Match the chart to the surrounding UI: token surface + ink, a hairline border, no
// heavy shadow. Precision lives here so the plotted marks stay clean.
function tooltipConfig(tokens: ChartTokens) {
  return {
    backgroundColor: tokens.surface,
    titleColor: tokens.axis,
    bodyColor: tokens.axis,
    borderColor: tokens.tooltipBorder,
    borderWidth: 1,
    padding: 8,
    displayColors: true,
    usePointStyle: true,
  };
}
