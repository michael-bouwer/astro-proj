import { Text } from "@chakra-ui/react";
import type { JobStatus } from "../../api/types";
import styles from "./StackingControls.module.scss";

// Mirrors pipeline/orchestrator.py's progress_cb call sequence
// (calibration -> reference -> aligning -> stacking -> color), plus a final
// "done" entry for the completed state. A run with dark/flat calibration
// both disabled never emits a "calibration" stage callback at all -- that's
// fine here, it just shows as retroactively complete once `stage` reaches
// "reference" or later, same as any skipped step in a checklist.
const STEPS: { stage: string; label: string }[] = [
  { stage: "calibration", label: "Building calibration masters" },
  { stage: "reference", label: "Loading reference frame" },
  { stage: "aligning", label: "Aligning frames" },
  { stage: "stacking", label: "Stacking" },
  { stage: "color", label: "Calibrating color" },
  { stage: "done", label: "Pipeline complete" },
];

export function PipelineStepsList({ job }: { job: JobStatus }) {
  const currentIndex = job.status === "done" ? STEPS.length : STEPS.findIndex((step) => step.stage === job.stage);

  return (
    <div className={styles.steps}>
      {STEPS.map((step, index) => {
        const isDone = job.status === "done" || index < currentIndex;
        const isCurrent = !isDone && index === currentIndex;
        const isErrored = isCurrent && job.status === "error";

        let labelClass = styles.stepLabel;
        if (isErrored) labelClass = styles.stepLabelError;
        else if (isCurrent) labelClass = styles.stepLabelCurrent;

        return (
          <div key={step.stage} className={styles.step}>
            <span className={isDone ? styles.tickDone : styles.tickPending}>{isDone ? "✓" : "○"}</span>
            <Text className={labelClass}>{step.label}</Text>
          </div>
        );
      })}
    </div>
  );
}
