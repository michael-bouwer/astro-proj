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

export function StatBar({ runResult }: { runResult: RunResult | null }) {
  if (!runResult) return null;

  return (
    <div className={styles.bar}>
      <Stat label="Stacked" value={`${runResult.stacked_frame_count} / ${runResult.light_frame_count}`} />
      <Stat label="Rejected frames" value={String(runResult.rejected_frame_count)} />
      <Stat label="SNR estimate" value={runResult.snr_db !== null ? `${runResult.snr_db.toFixed(1)} dB` : "n/a"} />
      <Stat
        label="Integration"
        value={runResult.integration_method === "sigma_clip" ? "Sigma clip average" : "Median"}
      />
    </div>
  );
}
