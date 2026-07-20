import { useEffect, useRef, useState } from "react";
import type { CropRect, TransformParams } from "../../api/types";
import { angleFromCenter, clamp, normalizeAngleDelta } from "../../utils/imageGeometry";
import styles from "./CropRotateOverlay.module.scss";

const FULL_FRAME: CropRect = { x: 0, y: 0, width: 1, height: 1 };
const MIN_CROP_SIZE = 0.08;
const MAX_ROTATION = 45;

type Corner = "nw" | "ne" | "sw" | "se";

function moveRect(rect: CropRect, dx: number, dy: number): CropRect {
  return {
    ...rect,
    x: clamp(rect.x + dx, 0, 1 - rect.width),
    y: clamp(rect.y + dy, 0, 1 - rect.height),
  };
}

function resizeFromCorner(rect: CropRect, corner: Corner, dx: number, dy: number): CropRect {
  let { x, y, width, height } = rect;

  if (corner === "nw" || corner === "sw") {
    const newX = x + dx;
    width = x + width - newX;
    x = newX;
  } else {
    width = width + dx;
  }

  if (corner === "nw" || corner === "ne") {
    const newY = y + dy;
    height = y + height - newY;
    y = newY;
  } else {
    height = height + dy;
  }

  if (width < MIN_CROP_SIZE) {
    if (corner === "nw" || corner === "sw") x -= MIN_CROP_SIZE - width;
    width = MIN_CROP_SIZE;
  }
  if (height < MIN_CROP_SIZE) {
    if (corner === "nw" || corner === "ne") y -= MIN_CROP_SIZE - height;
    height = MIN_CROP_SIZE;
  }

  x = clamp(x, 0, 1 - width);
  y = clamp(y, 0, 1 - height);
  width = clamp(width, MIN_CROP_SIZE, 1 - x);
  height = clamp(height, MIN_CROP_SIZE, 1 - y);

  return { x, y, width, height };
}

// Positions/transforms below are computed from live drag state, so they use
// the `style` prop -- a static SCSS class can't express a continuously
// variable pointer-driven value. Colors, borders, and fixed sizing stay in
// CropRotateOverlay.module.scss.
export function CropRotateOverlay({
  transformParams,
  onChange,
}: {
  transformParams: TransformParams;
  onChange: (params: TransformParams) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  const [liveCrop, setLiveCrop] = useState<CropRect>(transformParams.crop ?? FULL_FRAME);
  const [liveRotation, setLiveRotation] = useState(transformParams.rotationDeg);
  const [dragging, setDragging] = useState(false);

  // Refs mirror the state above so drag-end handlers can read the latest
  // value synchronously (the pointerup listener closes over the render at
  // drag-start time, which would otherwise see a stale value).
  const liveCropRef = useRef(liveCrop);
  const liveRotationRef = useRef(liveRotation);
  liveCropRef.current = liveCrop;
  liveRotationRef.current = liveRotation;

  // Reflect external changes (e.g. the Reset button) while not actively dragging.
  useEffect(() => {
    if (dragging) return;
    setLiveCrop(transformParams.crop ?? FULL_FRAME);
    setLiveRotation(transformParams.rotationDeg);
  }, [transformParams, dragging]);

  const commit = () => {
    onChange({ rotationDeg: liveRotationRef.current, crop: liveCropRef.current });
  };

  const startBoxDrag = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = containerRef.current!.getBoundingClientRect();
    const startClientX = e.clientX;
    const startClientY = e.clientY;
    const startCrop = liveCropRef.current;
    setDragging(true);

    const onMove = (ev: PointerEvent) => {
      const dx = (ev.clientX - startClientX) / rect.width;
      const dy = (ev.clientY - startClientY) / rect.height;
      setLiveCrop(moveRect(startCrop, dx, dy));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragging(false);
      commit();
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const startResizeDrag = (corner: Corner) => (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = containerRef.current!.getBoundingClientRect();
    const startClientX = e.clientX;
    const startClientY = e.clientY;
    const startCrop = liveCropRef.current;
    setDragging(true);

    const onMove = (ev: PointerEvent) => {
      const dx = (ev.clientX - startClientX) / rect.width;
      const dy = (ev.clientY - startClientY) / rect.height;
      setLiveCrop(resizeFromCorner(startCrop, corner, dx, dy));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragging(false);
      commit();
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const startRotateDrag = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = containerRef.current!.getBoundingClientRect();
    const crop = liveCropRef.current;
    const centerX = rect.left + (crop.x + crop.width / 2) * rect.width;
    const centerY = rect.top + (crop.y + crop.height / 2) * rect.height;
    const startAngle = angleFromCenter(centerX, centerY, e.clientX, e.clientY);
    const startRotation = liveRotationRef.current;
    setDragging(true);

    const onMove = (ev: PointerEvent) => {
      const currentAngle = angleFromCenter(centerX, centerY, ev.clientX, ev.clientY);
      const delta = normalizeAngleDelta(currentAngle - startAngle);
      setLiveRotation(clamp(startRotation + delta, -MAX_ROTATION, MAX_ROTATION));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragging(false);
      commit();
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const pct = (v: number) => `${v * 100}%`;

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.scrim} style={{ left: 0, top: 0, right: 0, height: pct(liveCrop.y) }} />
      <div className={styles.scrim} style={{ left: 0, top: pct(liveCrop.y + liveCrop.height), right: 0, bottom: 0 }} />
      <div
        className={styles.scrim}
        style={{ left: 0, top: pct(liveCrop.y), width: pct(liveCrop.x), height: pct(liveCrop.height) }}
      />
      <div
        className={styles.scrim}
        style={{
          left: pct(liveCrop.x + liveCrop.width),
          top: pct(liveCrop.y),
          right: 0,
          height: pct(liveCrop.height),
        }}
      />

      <div
        className={styles.box}
        style={{
          left: pct(liveCrop.x),
          top: pct(liveCrop.y),
          width: pct(liveCrop.width),
          height: pct(liveCrop.height),
        }}
        onPointerDown={startBoxDrag}
      >
        <div
          className={`${styles.handle} ${styles.handleNw}`}
          style={{ left: 0, top: 0, transform: "translate(-50%, -50%)" }}
          onPointerDown={startResizeDrag("nw")}
        />
        <div
          className={`${styles.handle} ${styles.handleNe}`}
          style={{ left: "100%", top: 0, transform: "translate(-50%, -50%)" }}
          onPointerDown={startResizeDrag("ne")}
        />
        <div
          className={`${styles.handle} ${styles.handleSw}`}
          style={{ left: 0, top: "100%", transform: "translate(-50%, -50%)" }}
          onPointerDown={startResizeDrag("sw")}
        />
        <div
          className={`${styles.handle} ${styles.handleSe}`}
          style={{ left: "100%", top: "100%", transform: "translate(-50%, -50%)" }}
          onPointerDown={startResizeDrag("se")}
        />
      </div>

      <div
        className={styles.rotateHandle}
        style={{
          left: pct(liveCrop.x + liveCrop.width / 2),
          top: pct(liveCrop.y + liveCrop.height / 2),
          transform: `translate(-50%, -50%) rotate(${liveRotation}deg)`,
        }}
        onPointerDown={startRotateDrag}
        title={`${liveRotation.toFixed(1)}°`}
      >
        <svg className={styles.rotateIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M21 12a9 9 0 1 1-3.5-7.14M21 3v6h-6" />
        </svg>
      </div>
    </div>
  );
}
