import type { RunParams, RunResult, Workspace } from "../api/types";

function sanitizeFilenamePart(value: string): string {
  // Strip characters invalid in Windows (and awkward on other OSes) filenames.
  return value.replace(/[\\/:*?"<>|]/g, "").trim();
}

function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Best-effort default export filename (no extension) -- workspace name plus
 * whatever stacking metadata is known. `runParams`/`runResult` reflect the
 * settings that produced the currently loaded master only when a pipeline run
 * happened this session; when a workspace is reopened with a pre-existing
 * master, callers fall back to the current Stacking tab's params, which is a
 * suggestion rather than a guarantee -- same caveat SaveVersionDialog accepts. */
export function buildDefaultExportFilename({
  workspace,
  runParams,
  runResult,
  date = new Date(),
}: {
  workspace: Workspace;
  runParams: RunParams | null;
  runResult: RunResult | null;
  date?: Date;
}): string {
  const parts = [sanitizeFilenamePart(workspace.name)];

  if (runParams) {
    parts.push(runParams.integration_method === "sigma_clip" ? "sigmaclip" : runParams.integration_method);
    parts.push(`s${runParams.sigma}`);
  }

  const frameCount = runResult?.stacked_frame_count ?? workspace.frame_counts.lights;
  if (frameCount) parts.push(`${frameCount}f`);

  parts.push(formatDate(date));

  return parts.filter((part) => part.length > 0).join("_");
}
