import { useEffect, useRef, useState } from "react";
import { Text } from "@chakra-ui/react";
import { previewUrl, referencePreviewUrl } from "../../api/client";
import type { EffectsParams, JobStatus, MasterDimensions, RunResult, StretchParams, TransformParams } from "../../api/types";
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
  const [fitSize, setFitSize] = useState<{ width: number; height: number } | null>(null);

  // .imageWrap shrink-wraps to the image's own rendered box via max-width/
  // max-height: 100% (see PreviewPanel.module.scss) so the crop overlay's
  // inset:0 lines up with the image exactly -- but a percentage max-height on
  // a shrink-to-fit box is circular (the wrap's own auto height depends on
  // the image, and the image's max-height depends on the wrap's height), so
  // browsers drop it and the image renders at its unconstrained intrinsic
  // size. In a canvas that's wide but short (a short browser window, say),
  // that let the image overflow past the bottom with no way to scroll to it.
  // Computing an explicit pixel size here breaks the circularity outright.
  useEffect(() => {
    const canvasEl = canvasRef.current;
    if (!canvasEl || !naturalSize) {
      setFitSize(null);
      return;
    }

    const recompute = () => {
      const cs = getComputedStyle(canvasEl);
      const availableWidth = canvasEl.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      const availableHeight = canvasEl.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
      if (availableWidth <= 0 || availableHeight <= 0) return;
      const scale = Math.min(availableWidth / naturalSize.width, availableHeight / naturalSize.height);
      setFitSize({ width: naturalSize.width * scale, height: naturalSize.height * scale });
    };

    recompute();
    const observer = new ResizeObserver(recompute);
    observer.observe(canvasEl);
    return () => observer.disconnect();
  }, [naturalSize]);

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
            style={fitSize ? { width: fitSize.width, height: fitSize.height } : undefined}
          >
            <img
              className={styles.image}
              src={imageSrc}
              alt="Stacked preview"
              onLoad={(e) => {
                const el = e.currentTarget;
                setNaturalSize({ width: el.naturalWidth, height: el.naturalHeight });
              }}
              style={cropEditing ? { transform: `rotate(${pendingTransform.rotationDeg}deg)` } : undefined}
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
