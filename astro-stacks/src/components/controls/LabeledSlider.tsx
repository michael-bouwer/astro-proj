import { useEffect, useRef } from "react";
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
  // Ark's NumberInput only takes `value` as a controlled prop up to a point --
  // once mounted, it keeps its own internal draft text for the input (so a
  // user's in-progress typing isn't clobbered by every render) and doesn't
  // reliably re-sync that draft when `value` changes from *outside* the
  // input itself (a workspace's saved settings loading in, or a Reset
  // button). The Slider right below this doesn't have that problem -- its
  // own `value` prop does sync correctly -- so only the number field needs
  // the workaround: push the formatted value into the DOM input directly
  // whenever it changes externally, skipped while the field is focused so it
  // never fights the user's own typing.
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const el = inputRef.current;
    if (el && document.activeElement !== el) {
      el.value = value.toFixed(precision);
    }
  }, [value, precision]);

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
            <NumberInput.Input ref={inputRef} />
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
