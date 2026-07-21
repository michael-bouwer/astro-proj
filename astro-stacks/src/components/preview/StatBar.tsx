import { Text } from "@chakra-ui/react";
import type { RunResult } from "../../api/types";
import styles from "./StatBar.module.scss";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.stat}>
      <Text className={styles.statLabel}>{label}</Text>
      <Text className={styles.statValue}>{value}</Text>
    </div>
  );
}

const INTEGRATION_LABELS: Record<RunResult["integration_method"], string> = {
  sigma_clip: "Sigma clip average",
  winsorized_sigma_clip: "Winsorized sigma clip",
  median: "Median",
};

export function StatBar({ runResult }: { runResult: RunResult | null }) {
  if (!runResult) return null;

  return (
    <div className={styles.bar}>
      <Stat label="Stacked" value={`${runResult.stacked_frame_count} / ${runResult.light_frame_count}`} />
      <Stat label="Failed to align" value={String(runResult.rejected_frame_count)} />
      {runResult.quality_rejected_count > 0 && (
        <Stat label="Rejected for quality" value={String(runResult.quality_rejected_count)} />
      )}
      <Stat label="SNR estimate" value={runResult.snr_db !== null ? `${runResult.snr_db.toFixed(1)} dB` : "n/a"} />
      <Stat label="Integration" value={INTEGRATION_LABELS[runResult.integration_method]} />
    </div>
  );
}
