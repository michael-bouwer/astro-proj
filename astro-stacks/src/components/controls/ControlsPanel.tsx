import { Tabs } from "@chakra-ui/react";
import type { JobStatus, RunParams, StretchParams } from "../../api/types";
import { StackingControls } from "./StackingControls";
import { StretchControls } from "./StretchControls";
import styles from "./ControlsPanel.module.scss";

export function ControlsPanel({
  runParams,
  onRunParamsChange,
  onRun,
  running,
  job,
  stretchParams,
  onStretchParamsChange,
}: {
  runParams: RunParams;
  onRunParamsChange: (params: RunParams) => void;
  onRun: () => void;
  running: boolean;
  job: JobStatus | null;
  stretchParams: StretchParams;
  onStretchParamsChange: (params: StretchParams) => void;
}) {
  return (
    <div className={styles.panel}>
      <Tabs.Root defaultValue="stacking">
        <Tabs.List className={styles.tabList}>
          <Tabs.Trigger value="stacking">Stacking</Tabs.Trigger>
          <Tabs.Trigger value="stretch">Stretch</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="stacking">
          <StackingControls params={runParams} onChange={onRunParamsChange} onRun={onRun} running={running} job={job} />
        </Tabs.Content>
        <Tabs.Content value="stretch">
          <StretchControls params={stretchParams} onChange={onStretchParamsChange} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
