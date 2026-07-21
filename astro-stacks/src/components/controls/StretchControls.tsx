import { Button, Text } from "@chakra-ui/react";
import type { StretchMethod, StretchParams } from "../../api/types";
import { LabeledSlider } from "./LabeledSlider";
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
          <LabeledSlider
            label="Target background"
            value={params.target_bkg}
            min={0.05}
            max={0.5}
            step={0.005}
            precision={3}
            onChange={(target_bkg) => onChange({ ...params, target_bkg })}
          />
          <Text className={styles.hint}>
            Black point and midtone are derived from the image's own statistics -- this only nudges how bright the
            sky background reads.
          </Text>
        </div>
      )}

      {params.method === "mtf" && (
        <div className={styles.field}>
          <LabeledSlider
            label="Midtone"
            value={params.midtone}
            min={0.01}
            max={0.9}
            step={0.005}
            precision={3}
            onChange={(midtone) => onChange({ ...params, midtone })}
          />
        </div>
      )}

      {params.method === "asinh" && (
        <div className={styles.field}>
          <LabeledSlider
            label="Asinh scale"
            value={params.scale}
            min={10}
            max={5000}
            step={10}
            precision={0}
            onChange={(scale) => onChange({ ...params, scale })}
          />
        </div>
      )}
    </div>
  );
}
