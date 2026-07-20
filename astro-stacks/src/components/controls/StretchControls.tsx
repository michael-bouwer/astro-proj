import { Button, Slider, Text } from "@chakra-ui/react";
import type { StretchMethod, StretchParams } from "../../api/types";
import styles from "./StretchControls.module.scss";

const METHODS: { value: StretchMethod; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "mtf", label: "MTF" },
  { value: "asinh", label: "Asinh" },
];

export function StretchControls({
  params,
  onChange,
}: {
  params: StretchParams;
  onChange: (params: StretchParams) => void;
}) {
  return (
    <div className={styles.section}>
      <div className={styles.field}>
        <Text className={styles.label}>Stretch method</Text>
        <div className={styles.segmented}>
          {METHODS.map((m) => (
            <Button
              key={m.value}
              size="sm"
              variant={params.method === m.value ? "solid" : "outline"}
              colorPalette="brand"
              onClick={() => onChange({ ...params, method: m.value })}
            >
              {m.label}
            </Button>
          ))}
        </div>
      </div>

      {params.method === "auto" && (
        <div className={styles.field}>
          <div className={styles.sliderLabelRow}>
            <Text className={styles.label}>Target background</Text>
            <Text className={styles.sliderValue}>{params.target_bkg.toFixed(3)}</Text>
          </div>
          <Slider.Root
            value={[params.target_bkg]}
            min={0.05}
            max={0.5}
            step={0.005}
            onValueChange={(details) => onChange({ ...params, target_bkg: details.value[0] })}
          >
            <Slider.Control>
              <Slider.Track>
                <Slider.Range />
              </Slider.Track>
              <Slider.Thumb index={0} />
            </Slider.Control>
          </Slider.Root>
          <Text className={styles.hint}>
            Black point and midtone are derived from the image's own statistics -- this only nudges how bright the
            sky background reads.
          </Text>
        </div>
      )}

      {params.method === "mtf" && (
        <div className={styles.field}>
          <div className={styles.sliderLabelRow}>
            <Text className={styles.label}>Midtone</Text>
            <Text className={styles.sliderValue}>{params.midtone.toFixed(3)}</Text>
          </div>
          <Slider.Root
            value={[params.midtone]}
            min={0.01}
            max={0.9}
            step={0.005}
            onValueChange={(details) => onChange({ ...params, midtone: details.value[0] })}
          >
            <Slider.Control>
              <Slider.Track>
                <Slider.Range />
              </Slider.Track>
              <Slider.Thumb index={0} />
            </Slider.Control>
          </Slider.Root>
        </div>
      )}

      {params.method === "asinh" && (
        <div className={styles.field}>
          <div className={styles.sliderLabelRow}>
            <Text className={styles.label}>Asinh scale</Text>
            <Text className={styles.sliderValue}>{Math.round(params.scale)}</Text>
          </div>
          <Slider.Root
            value={[params.scale]}
            min={10}
            max={5000}
            step={10}
            onValueChange={(details) => onChange({ ...params, scale: details.value[0] })}
          >
            <Slider.Control>
              <Slider.Track>
                <Slider.Range />
              </Slider.Track>
              <Slider.Thumb index={0} />
            </Slider.Control>
          </Slider.Root>
        </div>
      )}
    </div>
  );
}
