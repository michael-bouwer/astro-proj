import { Tabs } from "@chakra-ui/react";
import type { JobStatus, RunParams, StretchParams, TransformParams } from "../../api/types";
import { StackingControls } from "./StackingControls";
import { StretchControls } from "./StretchControls";
import { CropRotateControls } from "./CropRotateControls";
import styles from "./ControlsPanel.module.scss";

export function ControlsPanel({
  runParams,
  onRunParamsChange,
  onRun,
  running,
  job,
  stretchParams,
  onStretchParamsChange,
  transformParams,
  onTransformParamsChange,
  activeTab,
  onActiveTabChange,
}: {
  runParams: RunParams;
  onRunParamsChange: (params: RunParams) => void;
  onRun: () => void;
  running: boolean;
  job: JobStatus | null;
  stretchParams: StretchParams;
  onStretchParamsChange: (params: StretchParams) => void;
  transformParams: TransformParams;
  onTransformParamsChange: (params: TransformParams) => void;
  activeTab: string;
  onActiveTabChange: (tab: string) => void;
}) {
  return (
    <div className={styles.panel}>
      <Tabs.Root value={activeTab} onValueChange={(details) => onActiveTabChange(details.value)}>
        <Tabs.List className={styles.tabList}>
          <Tabs.Trigger value="stacking">Stacking</Tabs.Trigger>
          <Tabs.Trigger value="stretch">Stretch</Tabs.Trigger>
          <Tabs.Trigger value="crop">Crop</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="stacking">
          <StackingControls params={runParams} onChange={onRunParamsChange} onRun={onRun} running={running} job={job} />
        </Tabs.Content>
        <Tabs.Content value="stretch">
          <StretchControls params={stretchParams} onChange={onStretchParamsChange} />
        </Tabs.Content>
        <Tabs.Content value="crop">
          <CropRotateControls params={transformParams} onChange={onTransformParamsChange} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
