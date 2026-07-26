import { useEffect, useRef, useState } from "react";
import { Button, Text } from "@chakra-ui/react";
import { previewUrl, referencePreviewUrl } from "../../api/client";
import {
  DEFAULT_EFFECTS_PARAMS,
  type EffectsParams,
  type JobStatus,
  type MasterDimensions,
  type RunResult,
  type StretchParams,
  type TransformParams,
} from "../../api/types";
import { rotatedCanvasSize } from "../../utils/imageGeometry";
import { StatBar } from "./StatBar";
import { CropRotateOverlay } from "./CropRotateOverlay";
import styles from "./PreviewPanel.module.scss";

const UNROTATED: TransformParams = { rotationDeg: 0, crop: null };

type PreviewMode = "after" | "before" | "compare";

const MODE_LABELS: { mode: PreviewMode; label: string }[] = [
  { mode: "after", label: "After" },
  { mode: "before", label: "Before" },
  { mode: "compare", label: "Compare" },
];

// The requested preview size is rounded up to a multiple of this, so nudging
// the window (or dragging a panel divider) doesn't refetch the preview for
// every pixel of resize.
const PREVIEW_SIZE_QUANTUM = 256;
// Upper bound on what "fit to window" will ask for. Past this the extra detail
// isn't visible at fit scale, and inspecting detail is what 1:1 is for.
const PREVIEW_SIZE_CAP = 2560;

/** Longest-edge pixel budget for a preview filling a canvas of this size. */
function previewBudgetFor(canvas: { width: number; height: number }): number {
    const devicePixels = Math.max(canvas.width, canvas.height) * (window.devicePixelRatio || 1);
    const bucketed = Math.ceil(devicePixels / PREVIEW_SIZE_QUANTUM) * PREVIEW_SIZE_QUANTUM;
    return Math.min(PREVIEW_SIZE_CAP, Math.max(PREVIEW_SIZE_QUANTUM, bucketed));
}

export function PreviewPanel({
  workspaceId,
  masterLoaded,
  stretchParams,
  effectsParams,
  transformParams,
  cropEditing,
  pendingTransform,
  onPendingChange,
  masterDimensions,
  previewVersion,
  runResult,
  job,
}: {
  workspaceId: string;
  masterLoaded: boolean;
  stretchParams: StretchParams;
  effectsParams: EffectsParams;
  transformParams: TransformParams;
  cropEditing: boolean;
  pendingTransform: TransformParams;
  onPendingChange: (params: TransformParams) => void;
  masterDimensions: MasterDimensions | null;
  previewVersion: number;
  runResult: RunResult | null;
  job: JobStatus | null;
}) {
  const [referenceFailed, setReferenceFailed] = useState(false);
  const running = job?.status === "queued" || job?.status === "running";

  const canvasRef = useRef<HTMLDivElement>(null);
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);
  // .imageWrap's own box -- the bounding box the CSS-rotated image and crop
  // overlay need to fit inside without clipping (see boundingSize below).
  const [wrapSize, setWrapSize] = useState<{ width: number; height: number } | null>(null);
  // The <img> element's own rendered size -- while crop-editing this differs
  // from wrapSize (the unrotated image is smaller than its own rotated
  // bounding box for any angle that isn't a multiple of 180), so it needs
  // explicit sizing rather than filling the wrap.
  const [imageRenderSize, setImageRenderSize] = useState<{ width: number; height: number } | null>(null);

  // Before/after comparison -- "after" (current effects) is the default and
  // only mode available while crop-editing (its own overlay/rotation math
  // assumes the single, plain "after" image), so switching into crop-editing
  // forces this back rather than leaving a stale Before/Compare view active
  // underneath the crop UI.
  const [previewMode, setPreviewMode] = useState<PreviewMode>("after");
  const [comparePosition, setComparePosition] = useState(50);
  useEffect(() => {
    if (cropEditing) setPreviewMode("after");
  }, [cropEditing]);

  // Previews are normally rendered only as large as they're displayed (see
  // client.ts's previewUrl). "1:1" opts out for judging things that depend on
  // pixel scale -- noise reduction, star reduction, sharpen -- before export.
  const [fullResolution, setFullResolution] = useState(false);
  // The canvas's own available box, tracked so the requested preview size can
  // follow it. Quantised in previewBudgetFor so resizing doesn't refetch
  // constantly; null until first measured, in which case we just omit the
  // parameter and take the backend default rather than flashing a tiny image.
  const [canvasSize, setCanvasSize] = useState<{ width: number; height: number } | null>(null);
  useEffect(() => {
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;
    const measure = () => setCanvasSize({ width: canvasEl.clientWidth, height: canvasEl.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(canvasEl);
    return () => observer.disconnect();
  }, []);

  const previewMaxDimension = fullResolution ? 0 : canvasSize ? previewBudgetFor(canvasSize) : undefined;

  // Tracks a preview re-render the user explicitly asked for -- an Effects-tab
  // change, or toggling 1:1 (which at full resolution is the slowest render
  // the app does, so it especially wants feedback). Stretch/crop changes also
  // refetch the image but deliberately don't raise this. Skips the initial
  // mount so opening a workspace doesn't show "Applying..." before anything's
  // actually been changed.
  const [effectsRequestState, setEffectsRequestState] = useState<"idle" | "loading" | "error">("idle");
  const effectsMounted = useRef(false);
  useEffect(() => {
    if (!effectsMounted.current) {
      effectsMounted.current = true;
      return;
    }
    setEffectsRequestState("loading");
  }, [effectsParams, fullResolution]);

  const handleAfterLoad = (el: HTMLImageElement) => {
    setNaturalSize({ width: el.naturalWidth, height: el.naturalHeight });
    setEffectsRequestState("idle");
  };
  const handleAfterError = () => {
    setEffectsRequestState("error");
  };

  useEffect(() => {
    const canvasEl = canvasRef.current;
    if (!canvasEl || !naturalSize) {
      setWrapSize(null);
      setImageRenderSize(null);
      return;
    }

    const boundingSize = cropEditing
      ? rotatedCanvasSize(naturalSize.width, naturalSize.height, pendingTransform.rotationDeg)
      : naturalSize;

    const recompute = () => {
      const cs = getComputedStyle(canvasEl);
      const availableWidth = canvasEl.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      const availableHeight = canvasEl.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
      if (availableWidth <= 0 || availableHeight <= 0) return;
      const scale = Math.min(availableWidth / boundingSize.width, availableHeight / boundingSize.height);
      setWrapSize({ width: boundingSize.width * scale, height: boundingSize.height * scale });
      setImageRenderSize({ width: naturalSize.width * scale, height: naturalSize.height * scale });
    };

    recompute();
    const observer = new ResizeObserver(recompute);
    observer.observe(canvasEl);
    return () => observer.disconnect();
  }, [naturalSize, cropEditing, pendingTransform.rotationDeg]);

  // While actively editing a crop, the displayed image stays on a stable,
  // unrotated/uncropped reference fetched once from the backend -- rotation
  // is instead previewed live via a CSS transform (no network round-trip per
  // slider tick), and the crop box's 0-1 coordinate space is defined against
  // this same unrotated canvas, matching how pipeline/transform.py crops
  // *after* rotating. The real crop/rotation is only rendered server-side
  // (and only then reflected here) once "Apply Cropping" commits it. Effects
  // stay live either way, so brightness/contrast/etc. are still visible while
  // adjusting a crop.
  const effectiveTransform = cropEditing ? UNROTATED : transformParams;
  const imageSrc = previewUrl(
    workspaceId, stretchParams, previewVersion, effectiveTransform, effectsParams, previewMaxDimension,
  );
  // Same frame, same stretch/crop, but with effects reset to their neutral
  // no-op values -- the "Before" reference for the Before/After/Compare
  // toggle below. Its own URL never changes on an effects-tab edit, so it
  // doesn't refetch (or trip the loading indicator) when you're just tuning
  // Effects sliders.
  const beforeImageSrc = previewUrl(
    workspaceId, stretchParams, previewVersion, effectiveTransform, DEFAULT_EFFECTS_PARAMS, previewMaxDimension,
  );

  // 100 = fully "after", 0 = fully "before" -- Compare's slider is just the
  // in-between of those same two endpoints, so all three modes share one
  // clip-path calculation instead of three separate render branches.
  const revealPercent = previewMode === "after" ? 100 : previewMode === "before" ? 0 : comparePosition;

  return (
    <div className={styles.panel}>
      {masterLoaded && !running && !cropEditing && (
        <div className={styles.modeBar}>
          <div className={styles.segmented}>
            {MODE_LABELS.map(({ mode, label }) => (
              <Button
                key={mode}
                size="xs"
                variant={previewMode === mode ? "solid" : "outline"}
                colorPalette="brand"
                onClick={() => setPreviewMode(mode)}
              >
                {label}
              </Button>
            ))}
          </div>
          {/* Rendered as a segmented pair (rather than one toggle) so the
              active option is highlighted the same way the mode buttons above
              are -- which of the two you're in matters, since it changes how
              the scale-dependent effects look. */}
          <div className={styles.segmented}>
            <Button
              size="xs"
              variant={fullResolution ? "outline" : "solid"}
              colorPalette="brand"
              onClick={() => setFullResolution(false)}
              title="Render the preview at screen size. Much faster, but noise reduction, star reduction and sharpen are applied at that reduced scale, so they won't look exactly as they will on export."
            >
              Fit
            </Button>
            <Button
              size="xs"
              variant={fullResolution ? "solid" : "outline"}
              colorPalette="brand"
              onClick={() => setFullResolution(true)}
              title="Render at full resolution. Slower, but noise reduction, star reduction and sharpen look exactly as they will on export -- use this to judge them before exporting."
            >
              1:1
            </Button>
          </div>
        </div>
      )}

      <div ref={canvasRef} className={styles.canvas}>
        {!running && masterLoaded && effectsRequestState !== "idle" && (
          <div className={effectsRequestState === "error" ? styles.statusBadgeError : styles.statusBadge}>
            {effectsRequestState === "loading" ? (
              <>
                <span className={styles.spinner} />
                Applying...
              </>
            ) : (
              <>Preview failed</>
            )}
          </div>
        )}

        {running ? (
          <div className={styles.loading}>
            {referenceFailed ? (
              <div className={styles.blurredPlaceholder} />
            ) : (
              <img
                className={styles.blurredImage}
                src={referencePreviewUrl(workspaceId)}
                alt=""
                onError={() => setReferenceFailed(true)}
              />
            )}
            <div className={styles.scrim}>
              {/* Overall progress across the whole pipeline, not just the
                  current stage's own 0-100% -- the right-hand panel's
                  [stage] X% readout is the per-step one. */}
              <span className={styles.percentText}>{Math.round(job.overall_percent)}%</span>
              {job.message && <span className={styles.stageText}>{job.message}</span>}
            </div>
          </div>
        ) : masterLoaded ? (
          cropEditing ? (
            <div
              className={`${styles.imageWrap} ${styles.rotating}`}
              style={wrapSize ? { width: wrapSize.width, height: wrapSize.height } : undefined}
            >
              <img
                className={styles.image}
                src={imageSrc}
                alt="Stacked preview"
                onLoad={(e) => handleAfterLoad(e.currentTarget)}
                onError={handleAfterError}
                style={
                  imageRenderSize
                    ? {
                        position: "absolute",
                        top: "50%",
                        left: "50%",
                        width: imageRenderSize.width,
                        height: imageRenderSize.height,
                        maxWidth: "none",
                        maxHeight: "none",
                        transform: `translate(-50%, -50%) rotate(${pendingTransform.rotationDeg}deg)`,
                      }
                    : undefined
                }
              />
              <CropRotateOverlay
                pendingTransform={pendingTransform}
                onPendingChange={onPendingChange}
                masterDimensions={masterDimensions}
              />
            </div>
          ) : (
            <div
              className={`${styles.imageWrap} ${styles.layered}`}
              style={wrapSize ? { width: wrapSize.width, height: wrapSize.height } : undefined}
            >
              <img className={styles.layerImage} src={beforeImageSrc} alt="Before effects" />
              <img
                className={styles.layerImage}
                src={imageSrc}
                alt="After effects"
                onLoad={(e) => handleAfterLoad(e.currentTarget)}
                onError={handleAfterError}
                style={{ clipPath: `inset(0 ${100 - revealPercent}% 0 0)` }}
              />
              {previewMode === "compare" && (
                <>
                  <div className={styles.compareDivider} style={{ left: `${comparePosition}%` }} />
                  <input
                    type="range"
                    className={styles.compareSlider}
                    min={0}
                    max={100}
                    value={comparePosition}
                    onChange={(e) => setComparePosition(Number(e.target.value))}
                    aria-label="Before/after comparison position"
                  />
                </>
              )}
            </div>
          )
        ) : (
          <Text className={styles.placeholder}>Run the stack to see a preview here.</Text>
        )}
      </div>
      <StatBar runResult={runResult} />
    </div>
  );
}
