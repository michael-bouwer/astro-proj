import { useEffect, useRef, useState } from "react";
import { NumberInput, Slider, Text } from "@chakra-ui/react";
import { InfoTooltip } from "./InfoTooltip";
import styles from "./LabeledSlider.module.scss";

// Debounces onChange by default -- most sliders here drive a live preview
// re-fetch on every value change, and some of the effects behind that fetch
// (noise reduction, star reduction) are CPU-heavy, so firing that on every
// intermediate drag tick pegs the backend for the whole drag. The Crop tab's
// rotation slider passes debounceMs={0} to opt out: it only drives a local
// CSS transform while editing (see PreviewPanel.tsx), not a network request,
// so debouncing it would just make the rotation visibly lag the drag.
const DEFAULT_DEBOUNCE_MS = 300;

// Dragging a short slider track can't reliably land on a precise value --
// pairing it with an editable number field (type an exact value, or focus it
// and use the arrow keys to nudge by `step`) gives fine control the slider
// alone can't. Renders just the label row + number field + slider; callers
// keep their own field wrapper (and any hint text) around it, since not
// every slider has one.
export function LabeledSlider({
  label,
  tooltip,
  value,
  min,
  max,
  step,
  precision = 2,
  onChange,
  debounceMs = DEFAULT_DEBOUNCE_MS,
}: {
  label: string;
  tooltip?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  precision?: number;
  onChange: (value: number) => void;
  debounceMs?: number;
}) {
  // The slider thumb and number field both track this local value for
  // instant visual feedback while dragging/typing -- onChange (which the
  // caller typically wires to a preview re-fetch) only fires debounceMs
  // after the last change, so the UI never waits on it to feel responsive.
  const [localValue, setLocalValue] = useState(value);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Re-syncs from external changes (a workspace's saved settings loading in,
  // a Reset button, another control resetting this one) -- harmless to also
  // run right after this component's own debounced onChange fires, since by
  // then `value` has caught up to what localValue already is.
  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const commit = (next: number) => {
    setLocalValue(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (debounceMs <= 0) {
      onChange(next);
      return;
    }
    debounceRef.current = setTimeout(() => onChange(next), debounceMs);
  };

  // Ark's NumberInput only takes `value` as a controlled prop up to a point --
  // once mounted, it keeps its own internal draft text for the input (so a
  // user's in-progress typing isn't clobbered by every render) and doesn't
  // reliably re-sync that draft when `value` changes from *outside* the
  // input itself. The Slider right below this doesn't have that problem --
  // its own `value` prop does sync correctly -- so only the number field
  // needs the workaround: push the formatted value into the DOM input
  // directly whenever it changes, skipped while the field is focused so it
  // never fights the user's own typing.
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const el = inputRef.current;
    if (el && document.activeElement !== el) {
      el.value = localValue.toFixed(precision);
    }
  }, [localValue, precision]);

  return (
    <>
      <div className={styles.labelRow}>
        <div className={styles.labelGroup}>
          <Text className={styles.label}>{label}</Text>
          {tooltip && <InfoTooltip label={tooltip} />}
        </div>
        <NumberInput.Root
          size="xs"
          className={styles.numberInput}
          value={localValue.toFixed(precision)}
          min={min}
          max={max}
          step={step}
          onValueChange={(details) => {
            if (!Number.isNaN(details.valueAsNumber)) commit(details.valueAsNumber);
          }}
        >
          <NumberInput.Control>
            <NumberInput.Input ref={inputRef} />
          </NumberInput.Control>
        </NumberInput.Root>
      </div>
      <Slider.Root
        value={[localValue]}
        min={min}
        max={max}
        step={step}
        onValueChange={(details) => commit(details.value[0])}
      >
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
