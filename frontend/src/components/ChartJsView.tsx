import { useEffect, useRef } from "react";
import { Chart, registerables, type ChartType } from "chart.js";

Chart.register(...registerables);

const PALETTE = ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f", "#edc949"];

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

  // Instantiate once per chart type. Chart.js can't switch `type` on a live instance,
  // so only a kind change (bar↔line↔pie) rebuilds; data/title changes update in place
  // below — no teardown, so streaming patches and unrelated re-renders don't reset it.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const chart = new Chart(canvas, {
      type: kind as ChartType,
      data: { labels: [], datasets: [] },
      // maintainAspectRatio:false so the chart fills its sized .chart-box in the dashboard
      // grid — with the default true, side-by-side canvases overflow their cell and overlap.
      options: { responsive: true, maintainAspectRatio: false },
    });
    chartRef.current = chart;
    return () => {
      chart.destroy();
      chartRef.current = null;
    };
  }, [kind]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.data.labels = labels;
    chart.data.datasets = datasets.map((d, i) => styleDataset(d, i, kind));
    chart.options.plugins = { title: { display: !!title, text: title } };
    chart.update();
  }, [kind, title, labels, datasets]);

  // The relative, fixed-height box gives Chart.js a determinate size to resize against.
  return (
    <div className="chart-box">
      <canvas ref={canvasRef} />
    </div>
  );
}

/** Apply a simple colour palette so charts are legible without custom theming. */
function styleDataset(dataset: ChartDataset, index: number, kind: string) {
  const color = PALETTE[index % PALETTE.length];
  const backgroundColor =
    kind === "pie" ? dataset.data.map((_, i) => PALETTE[i % PALETTE.length]) : color;
  return { label: dataset.label, data: dataset.data, backgroundColor, borderColor: color };
}
