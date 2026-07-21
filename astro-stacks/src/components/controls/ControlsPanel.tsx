import { Tabs } from "@chakra-ui/react";
import type {
  JobStatus,
  MasterDimensions,
  RunParams,
  RunResult,
  StretchParams,
  TransformParams,
  Workspace,
} from "../../api/types";
import { StackingControls } from "./StackingControls";
import { StretchControls } from "./StretchControls";
import { CropRotateControls } from "./CropRotateControls";
import { ExportControls } from "./ExportControls";
import styles from "./ControlsPanel.module.scss";

export function ControlsPanel({
  workspace,
  masterLoaded,
  runParams,
  onRunParamsChange,
  onRun,
  running,
  job,
  stretchParams,
  onStretchParamsChange,
  transformParams,
  pendingTransform,
  onPendingChange,
  masterDimensions,
  cropEditing,
  onStartEditCrop,
  onApplyCrop,
  onCancelCrop,
  onResetCrop,
  lastCompletedRunParams,
  runResult,
  activeTab,
  onActiveTabChange,
}: {
  workspace: Workspace;
  masterLoaded: boolean;
  runParams: RunParams;
  onRunParamsChange: (params: RunParams) => void;
  onRun: () => void;
  running: boolean;
  job: JobStatus | null;
  stretchParams: StretchParams;
  onStretchParamsChange: (params: StretchParams) => void;
  transformParams: TransformParams;
  pendingTransform: TransformParams;
  onPendingChange: (params: TransformParams) => void;
  masterDimensions: MasterDimensions | null;
  cropEditing: boolean;
  onStartEditCrop: () => void;
  onApplyCrop: () => void;
  onCancelCrop: () => void;
  onResetCrop: () => void;
  lastCompletedRunParams: RunParams | null;
  runResult: RunResult | null;
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
          <Tabs.Trigger value="export">Export</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="stacking">
          <StackingControls params={runParams} onChange={onRunParamsChange} onRun={onRun} running={running} job={job} />
        </Tabs.Content>
        <Tabs.Content value="stretch">
          <StretchControls params={stretchParams} onChange={onStretchParamsChange} />
        </Tabs.Content>
        <Tabs.Content value="crop">
          <CropRotateControls
            transformParams={transformParams}
            pendingTransform={pendingTransform}
            onPendingChange={onPendingChange}
            masterDimensions={masterDimensions}
            masterLoaded={masterLoaded}
            cropEditing={cropEditing}
            onStartEdit={onStartEditCrop}
            onApply={onApplyCrop}
            onCancel={onCancelCrop}
            onReset={onResetCrop}
          />
        </Tabs.Content>
        <Tabs.Content value="export">
          <ExportControls
            workspaceId={workspace.id}
            workspace={workspace}
            masterLoaded={masterLoaded}
            masterDimensions={masterDimensions}
            stretchParams={stretchParams}
            transformParams={transformParams}
            runParams={lastCompletedRunParams}
            runResult={runResult}
          />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
