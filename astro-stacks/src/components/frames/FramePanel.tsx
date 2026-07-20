import { useEffect, useState } from "react";
import { Button, Heading, Text } from "@chakra-ui/react";
import { ApiError, getWorkspaceFrames } from "../../api/client";
import type { WorkspaceFrames } from "../../api/types";
import styles from "./FramePanel.module.scss";

const KIND_LABELS: Record<keyof WorkspaceFrames, string> = {
  lights: "Lights",
  darks: "Darks",
  flats: "Flats",
  biases: "Biases",
};

const KINDS = Object.keys(KIND_LABELS) as (keyof WorkspaceFrames)[];

export function FramePanel({ workspaceId }: { workspaceId: string }) {
  const [frames, setFrames] = useState<WorkspaceFrames | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = () => {
    setLoading(true);
    setError("");
    getWorkspaceFrames(workspaceId)
      .then(setFrames)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load frames"))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, [workspaceId]);

  const total = frames ? KINDS.reduce((sum, kind) => sum + frames[kind].length, 0) : 0;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <Heading size="sm">Frames{frames ? ` (${total})` : ""}</Heading>
        <Button size="xs" variant="ghost" onClick={refresh} loading={loading}>
          Refresh
        </Button>
      </div>

      {error && <Text className={styles.error}>{error}</Text>}

      {frames && (
        <div className={styles.groups}>
          {KINDS.map((kind) => (
            <div key={kind} className={styles.group}>
              <Text className={styles.groupLabel}>
                {KIND_LABELS[kind]} ({frames[kind].length})
              </Text>
              <ul className={styles.fileList}>
                {frames[kind].map((filename) => (
                  <li key={filename} className={styles.fileItem}>
                    {filename}
                  </li>
                ))}
                {frames[kind].length === 0 && <li className={styles.emptyItem}>none</li>}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
