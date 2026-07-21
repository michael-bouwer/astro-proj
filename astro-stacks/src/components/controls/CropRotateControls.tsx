import { Button, Slider, Text } from "@chakra-ui/react";
import type { MasterDimensions, TransformParams } from "../../api/types";
import {
  FULL_FRAME_CROP,
  centeredCropForAspect,
  centeredCropForSize,
  cropMatchesAspect,
  cropMatchesSize,
  simplifyRatio,
} from "../../utils/imageGeometry";
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
    return (
      <div className={styles.section}>
        <div className={styles.field}>
          <Text className={styles.label}>Rotation</Text>
          <Text className={styles.infoText}>{transformParams.rotationDeg.toFixed(1)}°</Text>
        </div>
        <div className={styles.field}>
          <Text className={styles.label}>Crop</Text>
          <Text className={styles.infoText}>
            {transformParams.crop && masterDimensions
              ? (() => {
                  const { width, height } = cropPixelSize(transformParams, masterDimensions);
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

  return (
    <div className={styles.section}>
      <div className={styles.field}>
        <div className={styles.sliderLabelRow}>
          <Text className={styles.label}>Rotation</Text>
          <Text className={styles.sliderValue}>{pendingTransform.rotationDeg.toFixed(1)}°</Text>
        </div>
        <Slider.Root
          value={[pendingTransform.rotationDeg]}
          min={-180}
          max={180}
          step={0.1}
          onValueChange={(details) => onPendingChange({ ...pendingTransform, rotationDeg: details.value[0] })}
        >
          <Slider.Control>
            <Slider.Track>
              <Slider.Range />
            </Slider.Track>
            <Slider.Thumb index={0} />
          </Slider.Control>
        </Slider.Root>
      </div>

      <div className={styles.field}>
        <Text className={styles.label}>Aspect ratio</Text>
        <div className={styles.presetRow}>
          {ASPECT_PRESETS.map((preset) => {
            const isActive =
              preset.aspect == null
                ? !pendingTransform.crop
                : !!pendingTransform.crop &&
                  !!masterDimensions &&
                  cropMatchesAspect(pendingTransform.crop, preset.aspect, masterDimensions.width, masterDimensions.height);
            return (
              <Button
                key={preset.label}
                size="sm"
                variant={isActive ? "solid" : "outline"}
                colorPalette="brand"
                disabled={!masterDimensions}
                onClick={() =>
                  onPendingChange({
                    ...pendingTransform,
                    crop:
                      preset.aspect == null || !masterDimensions
                        ? null
                        : centeredCropForAspect(
                            preset.aspect,
                            pendingTransform.crop ?? FULL_FRAME_CROP,
                            masterDimensions.width,
                            masterDimensions.height,
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
            const bigEnough = !!masterDimensions && masterDimensions.width >= preset.width && masterDimensions.height >= preset.height;
            const isActive =
              bigEnough &&
              !!pendingTransform.crop &&
              !!masterDimensions &&
              cropMatchesSize(pendingTransform.crop, preset.width, preset.height, masterDimensions.width, masterDimensions.height);
            return (
              <Button
                key={preset.label}
                size="sm"
                variant={isActive ? "solid" : "outline"}
                colorPalette="brand"
                disabled={!bigEnough}
                onClick={() =>
                  masterDimensions &&
                  onPendingChange({
                    ...pendingTransform,
                    crop: centeredCropForSize(
                      preset.width,
                      preset.height,
                      pendingTransform.crop ?? FULL_FRAME_CROP,
                      masterDimensions.width,
                      masterDimensions.height,
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
          {masterDimensions
            ? `Source is ${masterDimensions.width} × ${masterDimensions.height} px -- resolutions above that are disabled.`
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
