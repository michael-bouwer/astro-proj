import { Button, Slider, Text } from "@chakra-ui/react";
import type { TransformParams } from "../../api/types";
import styles from "./CropRotateControls.module.scss";

export function CropRotateControls({
  params,
  onChange,
}: {
  params: TransformParams;
  onChange: (params: TransformParams) => void;
}) {
  return (
    <div className={styles.section}>
      <div className={styles.field}>
        <div className={styles.sliderLabelRow}>
          <Text className={styles.label}>Rotation</Text>
          <Text className={styles.sliderValue}>{params.rotationDeg.toFixed(1)}°</Text>
        </div>
        <Slider.Root
          value={[params.rotationDeg]}
          min={-45}
          max={45}
          step={0.1}
          onValueChange={(details) => onChange({ ...params, rotationDeg: details.value[0] })}
        >
          <Slider.Control>
            <Slider.Track>
              <Slider.Range />
            </Slider.Track>
            <Slider.Thumb index={0} />
          </Slider.Control>
        </Slider.Root>
        <Text className={styles.hint}>
          Drag the handle in the middle of the image to straighten by eye, or fine-tune here.
        </Text>
      </div>

      <div className={styles.field}>
        <Text className={styles.label}>Crop</Text>
        <Text className={styles.cropReadout}>
          {params.crop
            ? `${(params.crop.width * 100).toFixed(0)}% × ${(params.crop.height * 100).toFixed(0)}% of frame`
            : "Full frame -- drag a corner handle on the image to start cropping"}
        </Text>
      </div>

      <Button
        variant="outline"
        onClick={() => onChange({ rotationDeg: 0, crop: null })}
        disabled={params.rotationDeg === 0 && !params.crop}
      >
        Reset
      </Button>
    </div>
  );
}
