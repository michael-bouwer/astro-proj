import { Button, Slider, Text } from "@chakra-ui/react";
import { DEFAULT_EFFECTS_PARAMS, type EffectsParams } from "../../api/types";
import styles from "./EffectsControls.module.scss";

const FIELDS: {
  key: keyof EffectsParams;
  label: string;
  min: number;
  max: number;
  format: (v: number) => string;
}[] = [
  { key: "brightness", label: "Brightness", min: -1, max: 1, format: (v) => v.toFixed(2) },
  { key: "contrast", label: "Contrast", min: -1, max: 1, format: (v) => v.toFixed(2) },
  { key: "saturation", label: "Saturation", min: 0, max: 2, format: (v) => v.toFixed(2) },
  { key: "sharpen", label: "Sharpen", min: 0, max: 1, format: (v) => v.toFixed(2) },
];

export function EffectsControls({
  params,
  onChange,
}: {
  params: EffectsParams;
  onChange: (params: EffectsParams) => void;
}) {
  const isDefault = FIELDS.every((field) => params[field.key] === DEFAULT_EFFECTS_PARAMS[field.key]);

  return (
    <div className={styles.section}>
      {FIELDS.map((field) => (
        <div className={styles.field} key={field.key}>
          <div className={styles.sliderLabelRow}>
            <Text className={styles.label}>{field.label}</Text>
            <Text className={styles.sliderValue}>{field.format(params[field.key])}</Text>
          </div>
          <Slider.Root
            value={[params[field.key]]}
            min={field.min}
            max={field.max}
            step={0.01}
            onValueChange={(details) => onChange({ ...params, [field.key]: details.value[0] })}
          >
            <Slider.Control>
              <Slider.Track>
                <Slider.Range />
              </Slider.Track>
              <Slider.Thumb index={0} />
            </Slider.Control>
          </Slider.Root>
        </div>
      ))}

      <Button variant="outline" onClick={() => onChange(DEFAULT_EFFECTS_PARAMS)} disabled={isDefault}>
        Reset
      </Button>
    </div>
  );
}
