import { Button } from "@chakra-ui/react";
import { DEFAULT_EFFECTS_PARAMS, type EffectsParams } from "../../api/types";
import { LabeledSlider } from "./LabeledSlider";
import styles from "./EffectsControls.module.scss";

const FIELDS: {
  key: keyof EffectsParams;
  label: string;
  min: number;
  max: number;
}[] = [
  { key: "brightness", label: "Brightness", min: -1, max: 1 },
  { key: "contrast", label: "Contrast", min: -1, max: 1 },
  { key: "saturation", label: "Saturation", min: 0, max: 2 },
  { key: "sharpen", label: "Sharpen", min: 0, max: 1 },
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
          <LabeledSlider
            label={field.label}
            value={params[field.key]}
            min={field.min}
            max={field.max}
            step={0.01}
            onChange={(value) => onChange({ ...params, [field.key]: value })}
          />
        </div>
      ))}

      <Button variant="outline" onClick={() => onChange(DEFAULT_EFFECTS_PARAMS)} disabled={isDefault}>
        Reset
      </Button>
    </div>
  );
}
