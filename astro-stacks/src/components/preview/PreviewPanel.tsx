import { useState } from "react";
import { Text } from "@chakra-ui/react";
import { previewUrl, referencePreviewUrl } from "../../api/client";
import type { JobStatus, RunResult, StretchParams } from "../../api/types";
import { StatBar } from "./StatBar";
import styles from "./PreviewPanel.module.scss";

export function PreviewPanel({
  workspaceId,
  masterLoaded,
  stretchParams,
  previewVersion,
  runResult,
  job,
}: {
  workspaceId: string;
  masterLoaded: boolean;
  stretchParams: StretchParams;
  previewVersion: number;
  runResult: RunResult | null;
  job: JobStatus | null;
}) {
  const [referenceFailed, setReferenceFailed] = useState(false);
  const running = job?.status === "queued" || job?.status === "running";

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
          <img
            className={styles.image}
            src={previewUrl(workspaceId, stretchParams, previewVersion)}
            alt="Stacked preview"
          />
        ) : (
          <Text className={styles.placeholder}>Run the stack to see a preview here.</Text>
        )}
      </div>
      <StatBar runResult={runResult} />
    </div>
  );
}
