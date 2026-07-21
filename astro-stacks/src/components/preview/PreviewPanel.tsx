import { useState } from "react";
import { Text } from "@chakra-ui/react";
import { previewUrl, referencePreviewUrl } from "../../api/client";
import type { JobStatus, MasterDimensions, RunResult, StretchParams, TransformParams } from "../../api/types";
import { StatBar } from "./StatBar";
import { CropRotateOverlay } from "./CropRotateOverlay";
import styles from "./PreviewPanel.module.scss";

const UNROTATED: TransformParams = { rotationDeg: 0, crop: null };

export function PreviewPanel({
  workspaceId,
  masterLoaded,
  stretchParams,
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

  // While actively editing a crop, the displayed image stays on a stable,
  // unrotated/uncropped reference fetched once from the backend -- rotation
  // is instead previewed live via a CSS transform (no network round-trip per
  // slider tick), and the crop box's 0-1 coordinate space is defined against
  // this same unrotated canvas, matching how pipeline/transform.py crops
  // *after* rotating. The real crop/rotation is only rendered server-side
  // (and only then reflected here) once "Apply Cropping" commits it.
  const imageSrc = cropEditing
    ? previewUrl(workspaceId, stretchParams, previewVersion, UNROTATED)
    : previewUrl(workspaceId, stretchParams, previewVersion, transformParams);

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
          <div className={cropEditing ? `${styles.imageWrap} ${styles.rotating}` : styles.imageWrap}>
            <img
              className={styles.image}
              src={imageSrc}
              alt="Stacked preview"
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
