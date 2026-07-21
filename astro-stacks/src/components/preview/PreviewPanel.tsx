import { useEffect, useRef, useState } from "react";
import { Text } from "@chakra-ui/react";
import { previewUrl, referencePreviewUrl } from "../../api/client";
import type { EffectsParams, JobStatus, MasterDimensions, RunResult, StretchParams, TransformParams } from "../../api/types";
import { rotatedCanvasSize } from "../../utils/imageGeometry";
import { StatBar } from "./StatBar";
import { CropRotateOverlay } from "./CropRotateOverlay";
import styles from "./PreviewPanel.module.scss";

const UNROTATED: TransformParams = { rotationDeg: 0, crop: null };

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

  // .imageWrap shrink-wraps to the image's own rendered box via max-width/
  // max-height: 100% (see PreviewPanel.module.scss) so the crop overlay's
  // inset:0 lines up with the image exactly -- but a percentage max-height on
  // a shrink-to-fit box is circular (the wrap's own auto height depends on
  // the image, and the image's max-height depends on the wrap's height), so
  // browsers drop it and the image renders at its unconstrained intrinsic
  // size. In a canvas that's wide but short (a short browser window, say),
  // that let the image overflow past the bottom with no way to scroll to it.
  // Computing an explicit pixel size here breaks the circularity outright.
  //
  // While crop-editing, the wrap is sized to the *rotated* bounding box
  // (rotatedCanvasSize), not the raw natural size -- otherwise a CSS-rotated
  // wide image (e.g. a 90-degree rotation) would overflow a wrap still sized
  // for its original, now-wrong-aspect footprint, clipping off whatever
  // doesn't fit (the top and bottom, for a 90-degree rotation). This mirrors
  // pipeline/transform.py's rotate(), which expands the canvas the same way,
  // so the live preview and the actually-applied result agree.
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
  const imageSrc = cropEditing
    ? previewUrl(workspaceId, stretchParams, previewVersion, UNROTATED, effectsParams)
    : previewUrl(workspaceId, stretchParams, previewVersion, transformParams, effectsParams);

  return (
    <div className={styles.panel}>
      <div ref={canvasRef} className={styles.canvas}>
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
          <div
            className={cropEditing ? `${styles.imageWrap} ${styles.rotating}` : styles.imageWrap}
            style={wrapSize ? { width: wrapSize.width, height: wrapSize.height } : undefined}
          >
            <img
              className={styles.image}
              src={imageSrc}
              alt="Stacked preview"
              onLoad={(e) => {
                const el = e.currentTarget;
                setNaturalSize({ width: el.naturalWidth, height: el.naturalHeight });
              }}
              style={
                cropEditing && imageRenderSize
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
            {cropEditing && (
              <CropRotateOverlay
                pendingTransform={pendingTransform}
                onPendingChange={onPendingChange}
                masterDimensions={masterDimensions}
              />
            )}
          </div>
        ) : (
          <Text className={styles.placeholder}>Run the stack to see a preview here.</Text>
        )}
      </div>
      <StatBar runResult={runResult} />
    </div>
  );
}
