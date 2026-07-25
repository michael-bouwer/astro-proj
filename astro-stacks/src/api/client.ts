import type {
  EffectsParams,
  ExportParams,
  FrameKind,
  FrameQualityEntry,
  Histogram,
  JobStatus,
  MasterDimensions,
  RunParams,
  SaveVersionParams,
  SystemStats,
  TransformParams,
  Version,
  Workspace,
  WorkspaceFrames,
  WorkspaceSettings,
} from "./types";

export const API_BASE = "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export function listWorkspaces(): Promise<{ workspaces: Workspace[] }> {
  return request("/workspaces");
}

export function createWorkspace(name: string, source_path: string): Promise<Workspace> {
  return request("/workspaces", { method: "POST", body: JSON.stringify({ name, source_path }) });
}

export function getWorkspace(workspaceId: string): Promise<Workspace> {
  return request(`/workspaces/${workspaceId}`);
}

export function updateWorkspace(
  workspaceId: string,
  updates: { name?: string; source_path?: string }
): Promise<Workspace> {
  return request(`/workspaces/${workspaceId}`, { method: "PATCH", body: JSON.stringify(updates) });
}

export function deleteWorkspace(workspaceId: string): Promise<{ status: string }> {
  return request(`/workspaces/${workspaceId}`, { method: "DELETE" });
}

export function setWorkspaceCategories(workspaceId: string, categories: string[]): Promise<Workspace> {
  return request(`/workspaces/${workspaceId}/categories`, { method: "PUT", body: JSON.stringify({ categories }) });
}

export function getCategories(): Promise<{ categories: string[] }> {
  return request("/categories");
}

export function setWorkspaceFavourite(workspaceId: string, favourite: boolean): Promise<Workspace> {
  return request(`/workspaces/${workspaceId}/favourite`, { method: "PUT", body: JSON.stringify({ favourite }) });
}

export function reorderWorkspaces(workspaceIds: string[]): Promise<{ status: string }> {
  return request("/workspaces/reorder", { method: "POST", body: JSON.stringify({ workspace_ids: workspaceIds }) });
}

export function getWorkspaceFrames(workspaceId: string): Promise<WorkspaceFrames> {
  return request(`/workspaces/${workspaceId}/frames`);
}

export function getWorkspaceSettings(workspaceId: string): Promise<Partial<WorkspaceSettings>> {
  return request(`/workspaces/${workspaceId}/settings`);
}

export function saveWorkspaceSettings(workspaceId: string, settings: WorkspaceSettings): Promise<WorkspaceSettings> {
  return request(`/workspaces/${workspaceId}/settings`, {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export function getFrameQuality(workspaceId: string): Promise<{ frame_quality: FrameQualityEntry[] }> {
  return request(`/workspaces/${workspaceId}/frame_quality`);
}

export function getExcludedFrames(workspaceId: string): Promise<{ filenames: string[] }> {
  return request(`/workspaces/${workspaceId}/excluded_frames`);
}

export function saveExcludedFrames(workspaceId: string, filenames: string[]): Promise<{ filenames: string[] }> {
  return request(`/workspaces/${workspaceId}/excluded_frames`, {
    method: "PUT",
    body: JSON.stringify({ filenames }),
  });
}

export function framePreviewUrl(workspaceId: string, kind: FrameKind, filename: string): string {
  const query = new URLSearchParams({ kind, filename });
  return `${API_BASE}/workspaces/${workspaceId}/frames/preview?${query.toString()}`;
}

export function runPipeline(workspaceId: string, params: RunParams): Promise<{ job_id: string }> {
  return request(`/workspaces/${workspaceId}/pipeline/run`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function getJobStatus(workspaceId: string, jobId: string): Promise<JobStatus> {
  return request(`/workspaces/${workspaceId}/pipeline/status/${jobId}`);
}

export function loadMaster(workspaceId: string): Promise<{ status: string } & MasterDimensions> {
  return request(`/workspaces/${workspaceId}/load_master`, { method: "POST" });
}

export function previewUrl(
  workspaceId: string,
  params: { method: string; midtone: number; scale: number; target_bkg: number; shadow_clip: number },
  cacheBust: number,
  transform?: TransformParams,
  effects?: EffectsParams
): string {
  const query = new URLSearchParams({
    method: params.method,
    midtone: String(params.midtone),
    scale: String(params.scale),
    target_bkg: String(params.target_bkg),
    shadow_clip: String(params.shadow_clip),
    t: String(cacheBust),
  });
  if (transform) {
    query.set("rotation", String(transform.rotationDeg));
    if (transform.crop) {
      query.set("crop_x", String(transform.crop.x));
      query.set("crop_y", String(transform.crop.y));
      query.set("crop_width", String(transform.crop.width));
      query.set("crop_height", String(transform.crop.height));
    }
  }
  if (effects) {
    query.set("brightness", String(effects.brightness));
    query.set("contrast", String(effects.contrast));
    query.set("saturation", String(effects.saturation));
    query.set("vibrance", String(effects.vibrance));
    query.set("star_reduction", String(effects.star_reduction));
    query.set("noise_reduction", String(effects.noise_reduction));
    query.set("upscale", String(effects.upscale));
    query.set("sharpen", String(effects.sharpen));
  }
  return `${API_BASE}/workspaces/${workspaceId}/preview?${query.toString()}`;
}

export function getHistogram(workspaceId: string, shadowClip: number, transform?: TransformParams): Promise<Histogram> {
  const query = new URLSearchParams({ shadow_clip: String(shadowClip) });
  if (transform) {
    query.set("rotation", String(transform.rotationDeg));
    if (transform.crop) {
      query.set("crop_x", String(transform.crop.x));
      query.set("crop_y", String(transform.crop.y));
      query.set("crop_width", String(transform.crop.width));
      query.set("crop_height", String(transform.crop.height));
    }
  }
  return request(`/workspaces/${workspaceId}/histogram?${query.toString()}`);
}

export function referencePreviewUrl(workspaceId: string): string {
  return `${API_BASE}/workspaces/${workspaceId}/reference_preview`;
}

export function saveVersion(workspaceId: string, params: SaveVersionParams): Promise<Version> {
  return request(`/workspaces/${workspaceId}/versions`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function listVersions(workspaceId: string): Promise<{ versions: Version[] }> {
  return request(`/workspaces/${workspaceId}/versions`);
}

export function versionImageUrl(workspaceId: string, versionId: string, variant: "thumbnail" | "export"): string {
  return `${API_BASE}/workspaces/${workspaceId}/versions/${versionId}/image?variant=${variant}`;
}

export function getSystemStats(): Promise<SystemStats> {
  return request("/system/stats");
}

export function exportWorkspace(workspaceId: string, params: ExportParams): Promise<{ status: string; path: string }> {
  return request(`/workspaces/${workspaceId}/export`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export { ApiError };
