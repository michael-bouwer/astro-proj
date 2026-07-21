import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getJobStatus, runPipeline } from "../api/client";
import type { JobStatus, RunParams } from "../api/types";

const POLL_INTERVAL_MS = 1000;

type PipelineJobsContextValue = {
  // The workspace currently running the pipeline, if any -- the backend is a
  // single Python process, so two workspaces stacking at once would fight
  // over the same CPU/RAM. Only one run is allowed at a time, app-wide.
  activeWorkspaceId: string | null;
  activeWorkspaceName: string | null;
  getJob: (workspaceId: string) => JobStatus | null;
  getLastRunParams: (workspaceId: string) => RunParams | null;
  startRun: (workspaceId: string, workspaceName: string, params: RunParams) => Promise<void>;
};

const PipelineJobsContext = createContext<PipelineJobsContextValue | null>(null);

export function PipelineJobsProvider({ children }: { children: ReactNode }) {
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [activeWorkspaceName, setActiveWorkspaceName] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Record<string, JobStatus>>({});
  const [runParamsByWorkspace, setRunParamsByWorkspace] = useState<Record<string, RunParams>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activeWorkspaceRef = useRef<{ id: string | null; name: string | null }>({ id: null, name: null });

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const setActive = (id: string | null, name: string | null) => {
    activeWorkspaceRef.current = { id, name };
    setActiveWorkspaceId(id);
    setActiveWorkspaceName(name);
  };

  const startRun = useCallback(async (workspaceId: string, workspaceName: string, params: RunParams) => {
    const active = activeWorkspaceRef.current;
    if (active.id && active.id !== workspaceId) {
      throw new Error(`"${active.name}" is currently stacking -- wait for it to finish first.`);
    }

    const { job_id } = await runPipeline(workspaceId, params);
    setActive(workspaceId, workspaceName);
    setRunParamsByWorkspace((prev) => ({ ...prev, [workspaceId]: params }));
    setJobs((prev) => ({
      ...prev,
      [workspaceId]: {
        status: "queued",
        stage: null,
        percent: 0,
        overall_percent: 0,
        message: null,
        result: null,
        error: null,
        workspace_id: workspaceId,
      },
    }));

    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJobStatus(workspaceId, job_id);
        setJobs((prev) => ({ ...prev, [workspaceId]: status }));
        if (status.status === "done" || status.status === "error") {
          stopPolling();
          setActive(null, null);
        }
      } catch {
        stopPolling();
        setActive(null, null);
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const getJob = useCallback((workspaceId: string) => jobs[workspaceId] ?? null, [jobs]);
  const getLastRunParams = useCallback(
    (workspaceId: string) => runParamsByWorkspace[workspaceId] ?? null,
    [runParamsByWorkspace],
  );

  return (
    <PipelineJobsContext.Provider
      value={{ activeWorkspaceId, activeWorkspaceName, getJob, getLastRunParams, startRun }}
    >
      {children}
    </PipelineJobsContext.Provider>
  );
}

export function usePipelineJobs(): PipelineJobsContextValue {
  const ctx = useContext(PipelineJobsContext);
  if (!ctx) throw new Error("usePipelineJobs must be used within a PipelineJobsProvider");
  return ctx;
}
