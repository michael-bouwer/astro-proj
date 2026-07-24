import { useEffect, useRef } from "react";
import type { Histogram as HistogramData } from "../../api/types";
import styles from "./Histogram.module.scss";

const CANVAS_WIDTH = 280;
const CANVAS_HEIGHT = 90;

// Renders straight onto a <canvas> rather than SVG bars -- three overlaid,
// per-channel fills with additive blending is simpler to get looking right
// as a canvas path than as a stack of SVG elements, and there's no need for
// per-bar interactivity here.
export function Histogram({ data }: { data: HistogramData | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    if (!data) return;

    const maxCount = Math.max(...data.b, ...data.g, ...data.r, 1e-6);
    const barWidth = CANVAS_WIDTH / data.bins;

    const drawChannel = (values: number[], color: string) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(0, CANVAS_HEIGHT);
      values.forEach((v, i) => {
        const y = CANVAS_HEIGHT - (v / maxCount) * CANVAS_HEIGHT;
        ctx.lineTo(i * barWidth, y);
        ctx.lineTo((i + 1) * barWidth, y);
      });
      ctx.lineTo(CANVAS_WIDTH, CANVAS_HEIGHT);
      ctx.closePath();
      ctx.fill();
    };

    ctx.globalCompositeOperation = "lighter";
    drawChannel(data.b, "rgba(90, 150, 255, 0.6)");
    drawChannel(data.g, "rgba(100, 230, 130, 0.6)");
    drawChannel(data.r, "rgba(255, 110, 110, 0.6)");
    ctx.globalCompositeOperation = "source-over";

    // Where the "auto" method's shadow clip currently lands -- lets you see
    // whether it's actually sitting at the base of the background peak or
    // cutting into it.
    const blackPointX = (data.black_point / data.display_max) * CANVAS_WIDTH;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(blackPointX, 0);
    ctx.lineTo(blackPointX, CANVAS_HEIGHT);
    ctx.stroke();
  }, [data]);

  return (
    <div className={styles.wrap}>
      <canvas ref={canvasRef} width={CANVAS_WIDTH} height={CANVAS_HEIGHT} className={styles.canvas} />
      {!data && <div className={styles.placeholder}>Histogram available once a master is loaded.</div>}
    </div>
  );
}
