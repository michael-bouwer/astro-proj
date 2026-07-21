import { useEffect, useState } from "react";
import { Text } from "@chakra-ui/react";
import { getSystemStats } from "../../api/client";
import type { SystemStats as SystemStatsData } from "../../api/types";
import styles from "./SystemStats.module.scss";

const POLL_INTERVAL_MS = 2000;
// Matches the level a user would actually call out ("my memory was on 85%") --
// flags the header stat instead of waiting until the OS itself is under pressure.
const WARNING_THRESHOLD = 85;

export function SystemStats() {
  const [stats, setStats] = useState<SystemStatsData | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      getSystemStats()
        .then((result) => {
          if (!cancelled) setStats(result);
        })
        .catch(() => {
          // Backend may not be reachable yet (or briefly) -- keep showing the
          // last good reading rather than flashing an error in the header.
        });
    };

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!stats) return null;

  return (
    <div
      className={styles.stats}
      title={`${stats.memory_used_gb.toFixed(1)} / ${stats.memory_total_gb.toFixed(1)} GB RAM used`}
    >
      <span className={styles.stat}>
        <Text as="span" className={styles.label}>
          CPU
        </Text>
        <Text as="span" className={stats.cpu_percent >= WARNING_THRESHOLD ? styles.valueWarning : styles.value}>
          {Math.round(stats.cpu_percent)}%
        </Text>
      </span>
      <span className={styles.stat}>
        <Text as="span" className={styles.label}>
          RAM
        </Text>
        <Text as="span" className={stats.memory_percent >= WARNING_THRESHOLD ? styles.valueWarning : styles.value}>
          {Math.round(stats.memory_percent)}%
        </Text>
      </span>
    </div>
  );
}
