import { useState } from "react";
import { Button, Checkbox, Dialog, Portal, Text, Textarea } from "@chakra-ui/react";
import { ApiError, saveVersion } from "../../api/client";
import type { RunParams, SaveVersionParams, StretchParams, TransformParams, Version } from "../../api/types";
import styles from "./SaveVersionDialog.module.scss";

export function SaveVersionDialog({
  open,
  onClose,
  workspaceId,
  stretchParams,
  transformParams,
  runParams,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  stretchParams: StretchParams;
  transformParams: TransformParams;
  runParams: RunParams | null;
  onSaved: (version: Version) => void;
}) {
  const [note, setNote] = useState("");
  const [fixHalos, setFixHalos] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleClose = () => {
    setNote("");
    setError("");
    onClose();
  };

  const handleSave = async () => {
    setSubmitting(true);
    setError("");
    try {
      const params: SaveVersionParams = {
        ...stretchParams,
        note: note.trim(),
        fix_halos: fixHalos,
        ...(runParams ?? {}),
        rotation: transformParams.rotationDeg,
        ...(transformParams.crop
          ? {
              crop_x: transformParams.crop.x,
              crop_y: transformParams.crop.y,
              crop_width: transformParams.crop.width,
              crop_height: transformParams.crop.height,
            }
          : {}),
      };
      const version = await saveVersion(workspaceId, params);
      setNote("");
      onSaved(version);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save version");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(details) => !details.open && handleClose()}>
      <Portal>
        <Dialog.Backdrop className={styles.backdrop} />
        <Dialog.Positioner className={styles.positioner}>
          <Dialog.Content className={styles.content}>
            <Dialog.Title>Save version</Dialog.Title>
            <Text className={styles.hint}>
              Records the current stretch ({stretchParams.method})
              {(transformParams.rotationDeg !== 0 || transformParams.crop) && " and crop/rotation"} as a new version
              with your note -- useful for tracking what changed between iterations.
            </Text>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Raised sigma to 3.5 to reject a satellite trail; switched to MTF 0.2"
              rows={4}
            />
            <Checkbox.Root checked={fixHalos} onCheckedChange={(details) => setFixHalos(details.checked === true)}>
              <Checkbox.HiddenInput />
              <Checkbox.Control />
              <Checkbox.Label>Fix star halos on export</Checkbox.Label>
            </Checkbox.Root>
            {error && <Text className={styles.error}>{error}</Text>}
            <div className={styles.footer}>
              <Button variant="ghost" onClick={handleClose}>
                Cancel
              </Button>
              <Button colorPalette="brand" onClick={handleSave} loading={submitting}>
                Save
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
