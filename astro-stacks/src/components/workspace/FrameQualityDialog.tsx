import { useEffect, useState } from "react";
import { Badge, Button, CloseButton, Drawer, Heading, Portal, Text } from "@chakra-ui/react";
import { ApiError, framePreviewUrl, getExcludedFrames, getFrameQuality, saveExcludedFrames } from "../../api/client";
import type { FrameQualityEntry, FrameQualityStatus } from "../../api/types";
import styles from "./FrameQualityDialog.module.scss";

const STATUS_LABEL: Record<FrameQualityStatus, string> = {
  included: "Included",
  quality_rejected: "Low SNR",
  failed_to_align: "Failed to align",
  manually_excluded: "Excluded",
};

const STATUS_COLOR: Record<FrameQualityStatus, string> = {
  included: "green",
  quality_rejected: "orange",
  failed_to_align: "red",
  manually_excluded: "gray",
};

export function FrameQualityDialog({
  open,
  onClose,
  workspaceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
}) {
  const [frameQuality, setFrameQuality] = useState<FrameQualityEntry[] | null>(null);
  // Filenames the user wants excluded from the *next* run -- seeded from the
  // last-saved exclusion set, not from each entry's `status`, since a frame's
  // displayed status reflects the *previous* run's outcome and may already be
  // stale relative to what's been toggled here since.
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    setSaved(false);
    Promise.all([getFrameQuality(workspaceId), getExcludedFrames(workspaceId)])
      .then(([qualityRes, excludedRes]) => {
        setFrameQuality(qualityRes.frame_quality);
        setExcluded(new Set(excludedRes.filenames));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load frame quality"));
  }, [open, workspaceId]);

  const toggle = (filename: string) => {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) {
        next.delete(filename);
      } else {
        next.add(filename);
      }
      return next;
    });
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const result = await saveExcludedFrames(workspaceId, Array.from(excluded));
      setExcluded(new Set(result.filenames));
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save exclusions");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer.Root open={open} onOpenChange={(details) => !details.open && onClose()} size="md">
      <Portal>
        <Drawer.Backdrop />
        <Drawer.Positioner>
          <Drawer.Content className={styles.content}>
            <Drawer.Header className={styles.header}>
              <Heading size="md">Frame quality</Heading>
              <Drawer.CloseTrigger asChild>
                <CloseButton size="sm" />
              </Drawer.CloseTrigger>
            </Drawer.Header>
            <Drawer.Body className={styles.body}>
              {error && <Text className={styles.error}>{error}</Text>}
              <Text className={styles.hint}>
                Uncheck a frame to exclude it from the next stacking run. Changes here only take effect the next time
                you run the stack.
              </Text>
              {frameQuality !== null && frameQuality.length === 0 && (
                <Text className={styles.empty}>No frame quality data yet -- run the pipeline first.</Text>
              )}
              {frameQuality?.map((entry) => (
                <label key={entry.filename} className={styles.item}>
                  <input
                    type="checkbox"
                    checked={!excluded.has(entry.filename)}
                    onChange={() => toggle(entry.filename)}
                  />
                  <img
                    className={styles.thumbnail}
                    src={framePreviewUrl(workspaceId, "lights", entry.filename)}
                    alt=""
                    onError={(event) => {
                      (event.currentTarget as HTMLImageElement).style.visibility = "hidden";
                    }}
                  />
                  <div className={styles.itemBody}>
                    <Text className={styles.itemFilename}>{entry.filename}</Text>
                    <div className={styles.itemMeta}>
                      <Badge colorPalette={STATUS_COLOR[entry.status]} size="sm">
                        {STATUS_LABEL[entry.status]}
                      </Badge>
                      {entry.snr_db !== null && <Text as="span">SNR {entry.snr_db.toFixed(1)} dB</Text>}
                    </div>
                  </div>
                </label>
              ))}
            </Drawer.Body>
            <Drawer.Footer className={styles.footer}>
              <Text className={styles.saveHint}>{saved ? "Saved." : ""}</Text>
              <Button colorPalette="brand" onClick={handleSave} loading={saving} disabled={frameQuality === null}>
                Save exclusions
              </Button>
            </Drawer.Footer>
          </Drawer.Content>
        </Drawer.Positioner>
      </Portal>
    </Drawer.Root>
  );
}
