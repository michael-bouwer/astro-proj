import { useState } from "react";
import { Text } from "@chakra-ui/react";
import { previewUrl, referencePreviewUrl } from "../../api/client";
import type { JobStatus, RunResult, StretchParams, TransformParams } from "../../api/types";
import { StatBar } from "./StatBar";
import { CropRotateOverlay } from "./CropRotateOverlay";
import styles from "./PreviewPanel.module.scss";

export function PreviewPanel({
  workspaceId,
  masterLoaded,
  stretchParams,
  transformParams,
  onTransformParamsChange,
  showCropOverlay,
  previewVersion,
  runResult,
  job,
}: {
  workspaceId: string;
  masterLoaded: boolean;
  stretchParams: StretchParams;
  transformParams: TransformParams;
  onTransformParamsChange: (params: TransformParams) => void;
  showCropOverlay: boolean;
  previewVersion: number;
  runResult: RunResult | null;
  job: JobStatus | null;
}) {
  const [referenceFailed, setReferenceFailed] = useState(false);
  const running = job?.status === "queued" || job?.status === "running";

  // While the crop overlay is showing, the displayed image must stay on a
  // stable, uncropped (rotation-only) reference frame -- otherwise every
  // committed crop shrinks the actual displayed image (which object-fit:
  // contain then scales back up to fill the canvas), and the box's 0-1
  // coordinate space gets reinterpreted against that already-cropped result
  // on the next edit instead of the original frame, drifting further with
  // each adjustment. The real crop only gets baked into what's shown once
  // you're not actively editing it (or when saving a version).
  const displayTransform: TransformParams = showCropOverlay
    ? { rotationDeg: transformParams.rotationDeg, crop: null }
    : transformParams;

  return (
    <div className={styles.panel}>
      <div className={styles.canvas}>
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
              <span className={styles.percentText}>{Math.round(job.percent)}%</span>
              {job.message && <span className={styles.stageText}>{job.message}</span>}
            </div>
          </div>
        ) : masterLoaded ? (
          <div className={styles.imageWrap}>
            <img
              className={styles.image}
              src={previewUrl(workspaceId, stretchParams, previewVersion, displayTransform)}
              alt="Stacked preview"
            />
            {showCropOverlay && (
              <CropRotateOverlay transformParams={transformParams} onChange={onTransformParamsChange} />
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
