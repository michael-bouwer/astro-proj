import { Button, Text } from "@chakra-ui/react";
import type { MasterDimensions, TransformParams } from "../../api/types";
import {
  FULL_FRAME_CROP,
  centeredCropForAspect,
  centeredCropForSize,
  cropMatchesAspect,
  cropMatchesSize,
  rotatedCanvasSize,
  simplifyRatio,
} from "../../utils/imageGeometry";
import { LabeledSlider } from "./LabeledSlider";
import styles from "./CropRotateControls.module.scss";

const ASPECT_PRESETS: { label: string; aspect: number | null }[] = [
  { label: "Free", aspect: null },
  { label: "1:1", aspect: 1 },
  { label: "4:3", aspect: 4 / 3 },
  { label: "3:2", aspect: 3 / 2 },
  { label: "16:9", aspect: 16 / 9 },
];

// Common display resolutions, laptop to 4K -- exact pixel crops (not just
// aspect ratios), so they're only offered when the source is actually big
// enough to produce that many real pixels.
const RESOLUTION_PRESETS: { label: string; width: number; height: number }[] = [
  { label: "1366×768", width: 1366, height: 768 },
  { label: "1920×1080", width: 1920, height: 1080 },
  { label: "2560×1440", width: 2560, height: 1440 },
  { label: "3840×2160", width: 3840, height: 2160 },
];

function cropPixelSize(transform: TransformParams, masterDimensions: MasterDimensions) {
  const crop = transform.crop ?? { x: 0, y: 0, width: 1, height: 1 };
  const width = Math.round(crop.width * masterDimensions.width);
  const height = Math.round(crop.height * masterDimensions.height);
  return { width, height };
}

export function CropRotateControls({
  transformParams,
  pendingTransform,
  onPendingChange,
  masterDimensions,
  masterLoaded,
  cropEditing,
  onStartEdit,
  onApply,
  onCancel,
  onReset,
}: {
  transformParams: TransformParams;
  pendingTransform: TransformParams;
  onPendingChange: (params: TransformParams) => void;
  masterDimensions: MasterDimensions | null;
  masterLoaded: boolean;
  cropEditing: boolean;
  onStartEdit: () => void;
  onApply: () => void;
  onCancel: () => void;
  onReset: () => void;
}) {
  const canReset = transformParams.rotationDeg !== 0 || !!transformParams.crop;

  if (!cropEditing) {
    // Crop fractions apply to the *rotated* canvas (pipeline/transform.py
    // rotates before cropping, and now expands the canvas to fit), so the
    // committed rotation needs to be folded in before turning those
    // fractions back into a pixel size.
    const committedDimensions = masterDimensions
      ? rotatedCanvasSize(masterDimensions.width, masterDimensions.height, transformParams.rotationDeg)
      : null;
    return (
      <div className={styles.section}>
        <div className={styles.field}>
          <Text className={styles.label}>Rotation</Text>
          <Text className={styles.infoText}>{transformParams.rotationDeg.toFixed(1)}°</Text>
        </div>
        <div className={styles.field}>
          <Text className={styles.label}>Crop</Text>
          <Text className={styles.infoText}>
            {transformParams.crop && committedDimensions
              ? (() => {
                  const { width, height } = cropPixelSize(transformParams, committedDimensions);
                  return `${width} × ${height} px · ${simplifyRatio(width, height)}`;
                })()
              : "Full frame"}
          </Text>
        </div>
        <Button variant="outline" onClick={onStartEdit} disabled={!masterLoaded}>
          Edit Crop
        </Button>
        <Button variant="ghost" onClick={onReset} disabled={!canReset}>
          Reset
        </Button>
      </div>
    );
  }

  // Same reasoning as committedDimensions above, but against the *pending*
  // rotation while it's actively being adjusted -- the crop overlay and
  // preview canvas are both sized to this same rotated bounding box (see
  // PreviewPanel.tsx), so presets/labels need to agree with what's on screen.
  const editingDimensions = masterDimensions
    ? rotatedCanvasSize(masterDimensions.width, masterDimensions.height, pendingTransform.rotationDeg)
    : null;

  return (
    <div className={styles.section}>
      <div className={styles.field}>
        <LabeledSlider
          label="Rotation"
          value={pendingTransform.rotationDeg}
          min={-180}
          max={180}
          step={0.1}
          precision={1}
          onChange={(rotationDeg) => onPendingChange({ ...pendingTransform, rotationDeg })}
        />
      </div>

      <div className={styles.field}>
        <Text className={styles.label}>Aspect ratio</Text>
        <div className={styles.presetRow}>
          {ASPECT_PRESETS.map((preset) => {
            const isActive =
              preset.aspect == null
                ? !pendingTransform.crop
                : !!pendingTransform.crop &&
                  !!editingDimensions &&
                  cropMatchesAspect(pendingTransform.crop, preset.aspect, editingDimensions.width, editingDimensions.height);
            return (
              <Button
                key={preset.label}
                size="sm"
                variant={isActive ? "solid" : "outline"}
                colorPalette="brand"
                disabled={!editingDimensions}
                onClick={() =>
                  onPendingChange({
                    ...pendingTransform,
                    crop:
                      preset.aspect == null || !editingDimensions
                        ? null
                        : centeredCropForAspect(
                            preset.aspect,
                            pendingTransform.crop ?? FULL_FRAME_CROP,
                            editingDimensions.width,
                            editingDimensions.height,
                          ),
                  })
                }
              >
                {preset.label}
              </Button>
            );
          })}
        </div>
        <Text className={styles.cropReadout}>
          {pendingTransform.crop
            ? `${(pendingTransform.crop.width * 100).toFixed(0)}% × ${(pendingTransform.crop.height * 100).toFixed(0)}% of frame`
            : "Full frame -- drag a corner handle on the image to start cropping"}
        </Text>
        <Text className={styles.hint}>Hold Shift while dragging a corner to keep the current aspect ratio.</Text>
      </div>

      <div className={styles.field}>
        <Text className={styles.label}>Common resolutions</Text>
        <div className={styles.presetRow}>
          {RESOLUTION_PRESETS.map((preset) => {
            const bigEnough =
              !!editingDimensions && editingDimensions.width >= preset.width && editingDimensions.height >= preset.height;
            const isActive =
              bigEnough &&
              !!pendingTransform.crop &&
              !!editingDimensions &&
              cropMatchesSize(pendingTransform.crop, preset.width, preset.height, editingDimensions.width, editingDimensions.height);
            return (
              <Button
                key={preset.label}
                size="sm"
                variant={isActive ? "solid" : "outline"}
                colorPalette="brand"
                disabled={!bigEnough}
                onClick={() =>
                  editingDimensions &&
                  onPendingChange({
                    ...pendingTransform,
                    crop: centeredCropForSize(
                      preset.width,
                      preset.height,
                      pendingTransform.crop ?? FULL_FRAME_CROP,
                      editingDimensions.width,
                      editingDimensions.height,
                    ),
                  })
                }
              >
                {preset.label}
              </Button>
            );
          })}
        </div>
        <Text className={styles.hint}>
          {editingDimensions
            ? `Source is ${editingDimensions.width} × ${editingDimensions.height} px -- resolutions above that are disabled.`
            : "Available once the master is loaded."}
        </Text>
      </div>

      <div className={styles.footer}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button colorPalette="brand" onClick={onApply}>
          Apply Cropping
        </Button>
      </div>
    </div>
  );
}
