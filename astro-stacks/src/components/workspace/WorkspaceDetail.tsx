import { useEffect, useRef, useState } from "react";
import { Text } from "@chakra-ui/react";
import { ApiError, deleteWorkspace, getJobStatus, getWorkspace, loadMaster, runPipeline } from "../../api/client";
import type {
  JobStatus,
  RunParams,
  RunResult,
  StretchParams,
  TransformParams,
  Version,
  Workspace,
} from "../../api/types";
import { FramePanel } from "../frames/FramePanel";
import { PreviewPanel } from "../preview/PreviewPanel";
import { ControlsPanel } from "../controls/ControlsPanel";
import { VersionHistoryDrawer } from "../versions/VersionHistoryDrawer";
import { SaveVersionDialog } from "../versions/SaveVersionDialog";
import { ConfirmDialog } from "../common/ConfirmDialog";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import { WorkspaceHeader } from "./WorkspaceHeader";
import styles from "./WorkspaceDetail.module.scss";

const DEFAULT_RUN_PARAMS: RunParams = {
  sigma: 3.0,
  apply_dark: true,
  apply_flat: true,
  integration_method: "sigma_clip",
};

const DEFAULT_STRETCH_PARAMS: StretchParams = {
  method: "auto",
  midtone: 0.25,
  scale: 1000,
  target_bkg: 0.25,
  shadow_clip: -2.8,
};

const DEFAULT_TRANSFORM_PARAMS: TransformParams = {
  rotationDeg: 0,
  crop: null,
};

export function WorkspaceDetail({
  workspaceId,
  onDeleted,
  onRenamed,
}: {
  workspaceId: string;
  onDeleted: () => void;
  onRenamed: (workspace: Workspace) => void;
}) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const [runParams, setRunParams] = useState<RunParams>(DEFAULT_RUN_PARAMS);
  const [lastCompletedRunParams, setLastCompletedRunParams] = useState<RunParams | null>(null);
  const [stretchParams, setStretchParams] = useState<StretchParams>(DEFAULT_STRETCH_PARAMS);
  const [transformParams, setTransformParams] = useState<TransformParams>(DEFAULT_TRANSFORM_PARAMS);
  const [activeControlsTab, setActiveControlsTab] = useState("stacking");

  const [job, setJob] = useState<JobStatus | null>(null);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [masterLoaded, setMasterLoaded] = useState(false);
  const [previewVersion, setPreviewVersion] = useState(0);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshWorkspace = () => {
    getWorkspace(workspaceId)
      .then(setWorkspace)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load workspace"));
  };

  useEffect(() => {
    refreshWorkspace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  useEffect(() => {
    if (workspace?.has_master && !masterLoaded) {
      loadMaster(workspaceId)
        .then(() => {
          setMasterLoaded(true);
          setPreviewVersion((v) => v + 1);
        })
        .catch(() => {
          // dataset may have changed since the master was written; leave the
          // "run the stack" placeholder showing rather than surfacing an error
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace?.has_master]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleRun = async () => {
    setError("");
    try {
      const { job_id } = await runPipeline(workspaceId, runParams);
      setJob({ status: "queued", stage: null, percent: 0, message: null, result: null, error: null, workspace_id: workspaceId });

      pollRef.current = setInterval(async () => {
        try {
          const status = await getJobStatus(workspaceId, job_id);
          setJob(status);

          if (status.status === "done") {
            if (pollRef.current) clearInterval(pollRef.current);
            setRunResult(status.result);
            setLastCompletedRunParams(runParams);
            await loadMaster(workspaceId);
            setMasterLoaded(true);
            setPreviewVersion((v) => v + 1);
            refreshWorkspace();
          } else if (status.status === "error") {
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch (err) {
          if (pollRef.current) clearInterval(pollRef.current);
          setError(err instanceof ApiError ? err.message : "Failed to poll job status");
        }
      }, 1000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start pipeline");
    }
  };

  const handleVersionSaved = (_version: Version) => {
    setSaveOpen(false);
    setHistoryOpen(true);
  };

  const running = job?.status === "queued" || job?.status === "running";

  if (error && !workspace) {
    return <Text className={styles.error}>{error}</Text>;
  }

  if (!workspace) {
    return <Text className={styles.status}>Loading workspace...</Text>;
  }

  return (
    <div className={styles.container}>
      <WorkspaceHeader
        workspace={workspace}
        onOpenHistory={() => setHistoryOpen(true)}
        onSaveVersion={() => setSaveOpen(true)}
        saveDisabled={!masterLoaded}
        onEdit={() => setEditOpen(true)}
        onDelete={() => setDeleteConfirmOpen(true)}
      />

      <div className={styles.body}>
        <FramePanel workspaceId={workspaceId} />
        <PreviewPanel
          workspaceId={workspaceId}
          masterLoaded={masterLoaded}
          stretchParams={stretchParams}
          transformParams={transformParams}
          onTransformParamsChange={setTransformParams}
          showCropOverlay={activeControlsTab === "crop"}
          previewVersion={previewVersion}
          runResult={runResult}
          job={job}
        />
        <ControlsPanel
          runParams={runParams}
          onRunParamsChange={setRunParams}
          onRun={handleRun}
          running={running}
          job={job}
          stretchParams={stretchParams}
          onStretchParamsChange={setStretchParams}
          transformParams={transformParams}
          onTransformParamsChange={setTransformParams}
          activeTab={activeControlsTab}
          onActiveTabChange={setActiveControlsTab}
        />
      </div>

      <VersionHistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} workspaceId={workspaceId} />
      <SaveVersionDialog
        open={saveOpen}
        onClose={() => setSaveOpen(false)}
        workspaceId={workspaceId}
        stretchParams={stretchParams}
        transformParams={transformParams}
        runParams={lastCompletedRunParams}
        onSaved={handleVersionSaved}
      />

      <CreateWorkspaceDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        editingWorkspace={workspace}
        onSaved={(updated) => {
          setWorkspace(updated);
          onRenamed(updated);
          setEditOpen(false);
        }}
      />
      <ConfirmDialog
        open={deleteConfirmOpen}
        title="Delete workspace?"
        message={`This removes "${workspace.name}" and all its saved versions. The source frames folder itself is not touched.`}
        confirmLabel="Delete"
        danger
        onConfirm={async () => {
          await deleteWorkspace(workspaceId);
          setDeleteConfirmOpen(false);
          onDeleted();
        }}
        onCancel={() => setDeleteConfirmOpen(false)}
      />
    </div>
  );
}
