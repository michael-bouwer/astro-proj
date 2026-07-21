import { Button, Checkbox, NativeSelect, Slider, Text } from "@chakra-ui/react";
import type { IntegrationMethod, JobStatus, RunParams } from "../../api/types";
import styles from "./StackingControls.module.scss";

export function StackingControls({
  params,
  onChange,
  onRun,
  running,
  job,
}: {
  params: RunParams;
  onChange: (params: RunParams) => void;
  onRun: () => void;
  running: boolean;
  job: JobStatus | null;
}) {
  return (
    <div className={styles.section}>
      <div className={styles.field}>
        <Text className={styles.label}>Alignment</Text>
        <Text className={styles.infoText}>Star pattern match (astroalign)</Text>
      </div>

      <div className={styles.field}>
        <Text className={styles.label}>Integration method</Text>
        <NativeSelect.Root size="sm">
          <NativeSelect.Field
            value={params.integration_method}
            onChange={(e) =>
              onChange({ ...params, integration_method: e.target.value as IntegrationMethod })
            }
          >
            <option value="sigma_clip">Sigma clip average</option>
            <option value="winsorized_sigma_clip">Winsorized sigma clip</option>
            <option value="median">Median</option>
          </NativeSelect.Field>
          <NativeSelect.Indicator />
        </NativeSelect.Root>
      </div>

      <div className={styles.field}>
        <div className={styles.sliderLabelRow}>
          <Text className={styles.label}>Rejection threshold</Text>
          <Text className={styles.sliderValue}>{params.sigma.toFixed(1)}σ</Text>
        </div>
        <Slider.Root
          value={[params.sigma]}
          min={1}
          max={5}
          step={0.1}
          onValueChange={(details) => onChange({ ...params, sigma: details.value[0] })}
        >
          <Slider.Control>
            <Slider.Track>
              <Slider.Range />
            </Slider.Track>
            <Slider.Thumb index={0} />
          </Slider.Control>
        </Slider.Root>
      </div>

      <div className={styles.checkboxes}>
        <Checkbox.Root
          checked={params.apply_dark}
          onCheckedChange={(details) => onChange({ ...params, apply_dark: details.checked === true })}
        >
          <Checkbox.HiddenInput />
          <Checkbox.Control />
          <Checkbox.Label>Apply dark calibration</Checkbox.Label>
        </Checkbox.Root>

        <Checkbox.Root
          checked={params.apply_flat}
          onCheckedChange={(details) => onChange({ ...params, apply_flat: details.checked === true })}
        >
          <Checkbox.HiddenInput />
          <Checkbox.Control />
          <Checkbox.Label>Apply flat calibration</Checkbox.Label>
        </Checkbox.Root>
      </div>

      <Button colorPalette="brand" onClick={onRun} loading={running} className={styles.runButton}>
        Run Stack
      </Button>

      {job && (
        <div className={styles.progress}>
          <Text className={styles.progressLine}>
            [{job.stage ?? job.status}] {job.percent.toFixed(0)}%
          </Text>
          {job.message && <Text className={styles.progressMessage}>{job.message}</Text>}
          {job.status === "error" && <Text className={styles.progressError}>{job.error}</Text>}
        </div>
      )}
    </div>
  );
}
