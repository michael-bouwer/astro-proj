import { useEffect, useRef, useState } from "react";
import { Button, Heading, Text } from "@chakra-ui/react";
import { ApiError, framePreviewUrl, getWorkspaceFrames } from "../../api/client";
import type { FrameKind, WorkspaceFrames } from "../../api/types";
import styles from "./FramePanel.module.scss";

const KIND_LABELS: Record<FrameKind, string> = {
  lights: "Lights",
  darks: "Darks",
  flats: "Flats",
  biases: "Biases",
};

const KINDS = Object.keys(KIND_LABELS) as FrameKind[];

const HOVER_DELAY_MS = 250;

type HoveredFrame = { kind: FrameKind; filename: string; top: number };

export function FramePanel({ workspaceId }: { workspaceId: string }) {
  const [frames, setFrames] = useState<WorkspaceFrames | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hoveredFrame, setHoveredFrame] = useState<HoveredFrame | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = () => {
    setLoading(true);
    setError("");
    getWorkspaceFrames(workspaceId)
      .then(setFrames)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load frames"))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, [workspaceId]);

  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    };
  }, []);

  const total = frames ? KINDS.reduce((sum, kind) => sum + frames[kind].length, 0) : 0;

  const handleEnter = (kind: FrameKind, filename: string, top: number) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    // Debounced so sweeping the mouse down a long list doesn't fire a raw
    // decode per row it passes over -- only the row the cursor settles on.
    hoverTimeoutRef.current = setTimeout(() => {
      setPreviewFailed(false);
      setHoveredFrame({ kind, filename, top });
    }, HOVER_DELAY_MS);
  };

  const handleLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setHoveredFrame(null);
  };

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
                  <li
                    key={filename}
                    className={styles.fileItem}
                    onMouseEnter={(e) => handleEnter(kind, filename, e.currentTarget.getBoundingClientRect().top)}
                    onMouseLeave={handleLeave}
                  >
                    {filename}
                  </li>
                ))}
                {frames[kind].length === 0 && <li className={styles.emptyItem}>none</li>}
              </ul>
            </div>
          ))}
        </div>
      )}

      {hoveredFrame && !previewFailed && (
        <div className={styles.hoverPreview} style={{ top: hoveredFrame.top }}>
          <img
            className={styles.hoverPreviewImage}
            src={framePreviewUrl(workspaceId, hoveredFrame.kind, hoveredFrame.filename)}
            alt={hoveredFrame.filename}
            onError={() => setPreviewFailed(true)}
          />
        </div>
      )}
    </div>
  );
}
