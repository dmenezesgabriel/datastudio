import { useEffect, useRef } from "react";
import { Chart, registerables, type ChartType } from "chart.js";

Chart.register(...registerables);

const PALETTE = ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f", "#edc949"];

export interface ChartDataset {
  label: string;
  data: number[];
}

export interface ChartJsProps {
  kind: "bar" | "line" | "pie";
  title: string;
  labels: string[];
  datasets: ChartDataset[];
}

/** Render a Chart.js chart into a canvas, rebuilding it when inputs change. */
export function ChartJsView({ kind, title, labels, datasets }: ChartJsProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const chart = new Chart(canvas, {
      type: kind as ChartType,
      data: { labels, datasets: datasets.map((d, i) => styleDataset(d, i, kind)) },
      // maintainAspectRatio:false so the chart fills its sized .chart-box in the dashboard
      // grid — with the default true, side-by-side canvases overflow their cell and overlap.
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { title: { display: !!title, text: title } },
      },
    });
    return () => chart.destroy();
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
