import { Button, Text } from "@chakra-ui/react";
import { DEFAULT_EFFECTS_PARAMS, type EffectsParams } from "../../api/types";
import { FieldLabel } from "./FieldLabel";
import { LabeledSlider } from "./LabeledSlider";
import { TabDescription } from "./TabDescription";
import styles from "./EffectsControls.module.scss";

type SliderField = {
  key: keyof EffectsParams;
  label: string;
  min: number;
  max: number;
  tooltip: string;
};

// Grouped, in the fixed order pipeline/effects.py's apply() actually runs
// them in -- not user-reorderable, but shown grouped/labeled so it's clear
// *why* Upscale sits where it does relative to everything else, per its own
// description below.
const COLOR_AND_TONE: SliderField[] = [
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
];

const DETAIL_AND_NOISE: SliderField[] = [
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
];

const UPSCALE_OPTIONS: { label: string; value: number }[] = [
  { label: "Off", value: 1 },
  { label: "1.5x", value: 1.5 },
  { label: "2x", value: 2 },
  { label: "3x", value: 3 },
];

const ALL_KEYS = Object.keys(DEFAULT_EFFECTS_PARAMS) as (keyof EffectsParams)[];

function SliderGroup({
  fields,
  params,
  onChange,
}: {
  fields: SliderField[];
  params: EffectsParams;
  onChange: (params: EffectsParams) => void;
}) {
  return (
    <>
      {fields.map((field) => (
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
    </>
  );
}

export function EffectsControls({
  params,
  onChange,
}: {
  params: EffectsParams;
  onChange: (params: EffectsParams) => void;
}) {
  const isDefault = ALL_KEYS.every((key) => params[key] === DEFAULT_EFFECTS_PARAMS[key]);

  return (
    <div className={styles.section}>
      <TabDescription>
        Simple display-space touch-ups applied last, after the stretch and star-halo fix -- for adjusting the
        already-stretched image's brightness/color/sharpness, not for anything measured from the linear stacked
        data. Like Stretch, these never modify the master file itself.
      </TabDescription>

      <div className={styles.group}>
        <div className={styles.groupHeader}>Color &amp; tone</div>
        <div className={styles.groupNote}>Order-independent -- these give the same result whether applied before or after Upscale below.</div>
        <SliderGroup fields={COLOR_AND_TONE} params={params} onChange={onChange} />
      </div>

      <div className={styles.group}>
        <div className={styles.groupHeader}>Detail &amp; noise</div>
        <div className={styles.groupNote}>
          Always run before Upscale -- tuned to the image's native pixel scale, so they act on full-detail pixels
          rather than an already-resized image.
        </div>
        <SliderGroup fields={DETAIL_AND_NOISE} params={params} onChange={onChange} />
      </div>

      <div className={styles.group}>
        <div className={styles.groupHeader}>Upscale</div>
        <div className={styles.field}>
          <FieldLabel
            label="Upscale"
            tooltip="Resizes the image up by this factor (plain Lanczos resampling, not AI detail synthesis -- see the note below). Off (1x) is a no-op. Runs after Color & tone and Detail & noise above, and before Sharpen below."
          />
          <Text className={styles.upscaleNote}>
            A geometric resize -- more pixels, not more detail -- so it tends to look slightly softer than the
            source at the new size. Sharpen below runs after this specifically to counteract that softening; a
            touch more Sharpen than you'd otherwise use is normal once Upscale is on.
          </Text>
          <div className={styles.segmented}>
            {UPSCALE_OPTIONS.map((option) => (
              <Button
                key={option.label}
                size="sm"
                variant={params.upscale === option.value ? "solid" : "outline"}
                colorPalette="brand"
                onClick={() => onChange({ ...params, upscale: option.value })}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.group}>
        <div className={styles.groupHeader}>Sharpen</div>
        <div className={styles.groupNote}>Always run after Upscale -- so it sharpens for the final output size, and can counteract the softening the resize introduces.</div>
        <SliderGroup
          fields={[
            {
              key: "sharpen",
              label: "Sharpen",
              min: 0,
              max: 1,
              tooltip: "Boosts local contrast at edges (an unsharp-mask-style sharpen) to bring out fine detail. Too high can introduce haloing around stars and edges.",
            },
          ]}
          params={params}
          onChange={onChange}
        />
      </div>

      <Button variant="outline" onClick={() => onChange(DEFAULT_EFFECTS_PARAMS)} disabled={isDefault}>
        Reset
      </Button>
    </div>
  );
}
