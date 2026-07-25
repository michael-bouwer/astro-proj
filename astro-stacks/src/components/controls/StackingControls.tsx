import { Button, Checkbox, NativeSelect, Slider, Text } from "@chakra-ui/react";
import type { IntegrationMethod, JobStatus, RunParams } from "../../api/types";
import { FieldLabel } from "./FieldLabel";
import { InfoTooltip } from "./InfoTooltip";
import { PipelineStepsList } from "./PipelineStepsList";
import { TabDescription } from "./TabDescription";
import styles from "./StackingControls.module.scss";

export function StackingControls({
  params,
  onChange,
  onRun,
  running,
  blockedByOtherWorkspace,
  activeWorkspaceName,
  job,
}: {
  params: RunParams;
  onChange: (params: RunParams) => void;
  onRun: () => void;
  running: boolean;
  blockedByOtherWorkspace: boolean;
  activeWorkspaceName: string | null;
  job: JobStatus | null;
}) {
  return (
    <div className={styles.section}>
      <TabDescription>
        Configures and runs the actual stacking pipeline: calibrates each light frame, aligns them to a common
        reference, and combines them into one linear master image. These settings only take effect on the next Run
        Stack -- an already-stacked master isn't changed until you run again.
      </TabDescription>

      <div className={styles.field}>
        <FieldLabel
          label="Alignment"
          tooltip="Fixed method: matches star patterns between frames (astroalign) to warp every light frame onto a common reference frame before combining. Not user-configurable."
        />
        <Text className={styles.infoText}>Star pattern match (astroalign)</Text>
      </div>

      <div className={styles.field}>
        <FieldLabel
          label="Integration method"
          tooltip="How the aligned frames are combined into one pixel value per position. Sigma clip average: rejects outlier pixels (satellite trails, cosmic rays) beyond the threshold below, then averages what's left. Winsorized sigma clip: similar, but clamps outliers to the threshold instead of dropping them -- steadier with few frames. Median: takes the middle value per pixel; robust but noisier than averaging."
        />
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
          <div className={styles.labelGroup}>
            <Text className={styles.label}>Rejection threshold</Text>
            <InfoTooltip label="How many standard deviations a pixel can differ from the local median before sigma clip/winsorized sigma clip treats it as an outlier and rejects (or clamps) it instead of averaging it in. Lower = more aggressive rejection; higher = keeps more data but lets more artifacts through. Has no effect when Integration method is Median." />
          </div>
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
        <div className={styles.checkboxRow}>
          <Checkbox.Root
            checked={params.apply_dark}
            onCheckedChange={(details) => onChange({ ...params, apply_dark: details.checked === true })}
          >
            <Checkbox.HiddenInput />
            <Checkbox.Control />
            <Checkbox.Label>Apply dark calibration</Checkbox.Label>
          </Checkbox.Root>
          <InfoTooltip label="Subtracts a master dark frame (built from your dark frames) from each light frame to remove sensor thermal noise and hot pixels. Turn off only if you have no dark frames for this dataset." />
        </div>

        <div className={styles.checkboxRow}>
          <Checkbox.Root
            checked={params.apply_flat}
            onCheckedChange={(details) => onChange({ ...params, apply_flat: details.checked === true })}
          >
            <Checkbox.HiddenInput />
            <Checkbox.Control />
            <Checkbox.Label>Apply flat calibration</Checkbox.Label>
          </Checkbox.Root>
          <InfoTooltip label="Divides each light frame by a normalized master flat frame to correct vignetting (darker corners) and dust shadows from the optical path. Turn off only if you have no flat frames for this dataset." />
        </div>
      </div>

      <Button
        colorPalette="brand"
        onClick={onRun}
        loading={running}
        disabled={blockedByOtherWorkspace}
        className={styles.runButton}
      >
        Run Stack
      </Button>
      {blockedByOtherWorkspace && (
        <Text className={styles.blockedMessage}>
          Currently stacking "{activeWorkspaceName}" -- wait for it to finish first.
        </Text>
      )}

      {job && (
        <>
          <div className={styles.progress}>
            <Text className={styles.progressLine}>
              [{job.stage ?? job.status}] {job.percent.toFixed(0)}%
            </Text>
            {job.message && <Text className={styles.progressMessage}>{job.message}</Text>}
            {job.status === "error" && <Text className={styles.progressError}>{job.error}</Text>}
          </div>
          <PipelineStepsList job={job} />
        </>
      )}
    </div>
  );
}
