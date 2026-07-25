import { Button } from "@chakra-ui/react";
import { DEFAULT_EFFECTS_PARAMS, type EffectsParams } from "../../api/types";
import { LabeledSlider } from "./LabeledSlider";
import { TabDescription } from "./TabDescription";
import styles from "./EffectsControls.module.scss";

const FIELDS: {
  key: keyof EffectsParams;
  label: string;
  min: number;
  max: number;
  tooltip: string;
}[] = [
  {
    key: "brightness",
    label: "Brightness",
    min: -1,
    max: 1,
    tooltip: "Shifts every pixel's value up or down by a flat amount, after the stretch. Positive brightens, negative darkens.",
  },
  {
    key: "contrast",
    label: "Contrast",
    min: -1,
    max: 1,
    tooltip: "Steepens or flattens the tonal curve around midgray, after the stretch. Positive increases contrast, negative flattens it.",
  },
  {
    key: "saturation",
    label: "Saturation",
    min: 0,
    max: 2,
    tooltip: "Scales color intensity uniformly. 1 = unchanged, 0 = grayscale, above 1 = more vivid color across the whole image, faint and strong signal alike.",
  },
  {
    key: "vibrance",
    label: "Vibrance",
    min: -1,
    max: 1,
    tooltip: "Like saturation, but weighted to affect already-muted colors more than already-vivid ones -- boosts faint nebulosity color without blowing out star cores that are already saturated.",
  },
  {
    key: "star_reduction",
    label: "Star reduction",
    min: 0,
    max: 1,
    tooltip: "Shrinks star sizes by blending each detected star's edge toward the surrounding background, so nebulosity reads more clearly through a busy star field. 0 = no effect.",
  },
  {
    key: "noise_reduction",
    label: "Noise reduction",
    min: 0,
    max: 1,
    tooltip: "Smooths background grain with an edge-preserving (bilateral) filter, with extra protection for star cores so they don't get smeared. Higher values smooth more aggressively.",
  },
  {
    key: "sharpen",
    label: "Sharpen",
    min: 0,
    max: 1,
    tooltip: "Boosts local contrast at edges (an unsharp-mask-style sharpen) to bring out fine detail. Too high can introduce haloing around stars and edges.",
  },
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
      <TabDescription>
        Simple display-space touch-ups applied last, after the stretch and star-halo fix -- for adjusting the
        already-stretched image's brightness/color/sharpness, not for anything measured from the linear stacked
        data. Like Stretch, these never modify the master file itself.
      </TabDescription>

      {FIELDS.map((field) => (
        <div className={styles.field} key={field.key}>
          <LabeledSlider
            label={field.label}
            tooltip={field.tooltip}
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
