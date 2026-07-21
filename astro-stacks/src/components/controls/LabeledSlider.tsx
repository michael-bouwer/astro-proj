import { NumberInput, Slider, Text } from "@chakra-ui/react";
import styles from "./LabeledSlider.module.scss";

// Dragging a short slider track can't reliably land on a precise value --
// pairing it with an editable number field (type an exact value, or focus it
// and use the arrow keys to nudge by `step`) gives fine control the slider
// alone can't. Renders just the label row + number field + slider; callers
// keep their own field wrapper (and any hint text) around it, since not
// every slider has one.
export function LabeledSlider({
  label,
  value,
  min,
  max,
  step,
  precision = 2,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  precision?: number;
  onChange: (value: number) => void;
}) {
  return (
    <>
      <div className={styles.labelRow}>
        <Text className={styles.label}>{label}</Text>
        <NumberInput.Root
          size="xs"
          className={styles.numberInput}
          value={value.toFixed(precision)}
          min={min}
          max={max}
          step={step}
          onValueChange={(details) => {
            if (!Number.isNaN(details.valueAsNumber)) onChange(details.valueAsNumber);
          }}
        >
          <NumberInput.Control>
            <NumberInput.Input />
          </NumberInput.Control>
        </NumberInput.Root>
      </div>
      <Slider.Root value={[value]} min={min} max={max} step={step} onValueChange={(details) => onChange(details.value[0])}>
        <Slider.Control>
          <Slider.Track>
            <Slider.Range />
          </Slider.Track>
          <Slider.Thumb index={0} />
        </Slider.Control>
      </Slider.Root>
    </>
  );
}
