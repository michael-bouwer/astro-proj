import { useRef } from "react";
import type { CropRect, MasterDimensions, TransformParams } from "../../api/types";
import { FULL_FRAME_CROP, clamp, rotatedCanvasSize } from "../../utils/imageGeometry";
import styles from "./CropRotateOverlay.module.scss";

const MIN_CROP_SIZE = 0.08;

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

/** Re-derives width/height from an already-resized rect so its *pixel* aspect
 * ratio (accounting for the frame's actual width/height, which need not be
 * square) matches `aspect`, anchored at the corner opposite the one being
 * dragged -- used while Shift is held. */
function lockAspect(rect: CropRect, corner: Corner, aspect: number, frameWidth: number, frameHeight: number): CropRect {
  const frameAspect = frameWidth / frameHeight;
  const rightEdge = rect.x + rect.width;
  const bottomEdge = rect.y + rect.height;

  let height = clamp((rect.width * frameAspect) / aspect, MIN_CROP_SIZE, 1);
  let width = clamp((height * aspect) / frameAspect, MIN_CROP_SIZE, 1);

  let x = corner === "nw" || corner === "sw" ? rightEdge - width : rect.x;
  let y = corner === "nw" || corner === "ne" ? bottomEdge - height : rect.y;

  x = clamp(x, 0, 1 - width);
  y = clamp(y, 0, 1 - height);

  return { x, y, width, height };
}

// Positions/transforms below are computed from live drag state, so they use
// the `style` prop -- a static SCSS class can't express a continuously
// variable pointer-driven value. Colors, borders, and fixed sizing stay in
// CropRotateOverlay.module.scss.
export function CropRotateOverlay({
  pendingTransform,
  onPendingChange,
  masterDimensions,
}: {
  pendingTransform: TransformParams;
  onPendingChange: (params: TransformParams) => void;
  masterDimensions: MasterDimensions | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const crop = pendingTransform.crop ?? FULL_FRAME_CROP;
  // This container is sized to the *rotated* bounding box (see
  // PreviewPanel.tsx), so crop.x/y/width/height fractions -- and any pixel
  // size or aspect-ratio math derived from masterDimensions -- need to be
  // read against that same rotated size, not the frame's original one.
  const editingDimensions = masterDimensions
    ? rotatedCanvasSize(masterDimensions.width, masterDimensions.height, pendingTransform.rotationDeg)
    : null;

  const setCrop = (next: CropRect) => onPendingChange({ ...pendingTransform, crop: next });

  const startBoxDrag = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = containerRef.current!.getBoundingClientRect();
    const startClientX = e.clientX;
    const startClientY = e.clientY;
    const startCrop = crop;

    const onMove = (ev: PointerEvent) => {
      const dx = (ev.clientX - startClientX) / rect.width;
      const dy = (ev.clientY - startClientY) / rect.height;
      setCrop(moveRect(startCrop, dx, dy));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
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
    const startCrop = crop;
    const startAspect =
      editingDimensions != null ? (startCrop.width * editingDimensions.width) / (startCrop.height * editingDimensions.height) : null;

    const onMove = (ev: PointerEvent) => {
      const dx = (ev.clientX - startClientX) / rect.width;
      const dy = (ev.clientY - startClientY) / rect.height;
      let next = resizeFromCorner(startCrop, corner, dx, dy);
      if (ev.shiftKey && startAspect != null && editingDimensions != null) {
        next = lockAspect(next, corner, startAspect, editingDimensions.width, editingDimensions.height);
      }
      setCrop(next);
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const pct = (v: number) => `${v * 100}%`;

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.scrim} style={{ left: 0, top: 0, right: 0, height: pct(crop.y) }} />
      <div className={styles.scrim} style={{ left: 0, top: pct(crop.y + crop.height), right: 0, bottom: 0 }} />
      <div className={styles.scrim} style={{ left: 0, top: pct(crop.y), width: pct(crop.x), height: pct(crop.height) }} />
      <div
        className={styles.scrim}
        style={{ left: pct(crop.x + crop.width), top: pct(crop.y), right: 0, height: pct(crop.height) }}
      />

      <div
        className={styles.box}
        style={{ left: pct(crop.x), top: pct(crop.y), width: pct(crop.width), height: pct(crop.height) }}
        onPointerDown={startBoxDrag}
      >
        {editingDimensions && (
          <div className={styles.dimensionLabel}>
            {Math.round(crop.width * editingDimensions.width)} × {Math.round(crop.height * editingDimensions.height)} px
          </div>
        )}
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
    </div>
  );
}
