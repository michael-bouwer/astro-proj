export type FrameCounts = {
  lights: number;
  darks: number;
  flats: number;
  biases: number;
};

export type Workspace = {
  id: string;
  name: string;
  source_path: string;
  created_at: string;
  updated_at: string;
  frame_counts: FrameCounts;
  has_master: boolean;
};

export type WorkspaceFrames = {
  lights: string[];
  darks: string[];
  flats: string[];
  biases: string[];
};

export type IntegrationMethod = "sigma_clip" | "median";

export type RunParams = {
  sigma: number;
  apply_dark: boolean;
  apply_flat: boolean;
  integration_method: IntegrationMethod;
};

export type RunResult = {
  output_path: string;
  light_frame_count: number;
  stacked_frame_count: number;
  rejected_frame_count: number;
  applied_dark: boolean;
  applied_flat: boolean;
  integration_method: IntegrationMethod;
  snr_db: number | null;
  width: number;
  height: number;
};

export type JobStatusValue = "queued" | "running" | "done" | "error";

export type JobStatus = {
  status: JobStatusValue;
  stage: string | null;
  percent: number;
  message: string | null;
  result: RunResult | null;
  error: string | null;
  workspace_id: string;
};

export type StretchMethod = "auto" | "mtf" | "asinh";

export type StretchParams = {
  method: StretchMethod;
  midtone: number;
  scale: number;
  target_bkg: number;
  shadow_clip: number;
};

// Normalized [0,1] fractions of the (rotated) image -- resolution-independent
// between the small preview JPEG and the full-res master.
export type CropRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type TransformParams = {
  rotationDeg: number;
  crop: CropRect | null;
};

// Simple display-space post-processing (brightness/contrast/saturation/sharpen),
// applied last -- after stretch and halo-fix. Each field's neutral/no-op value
// matches the backend's default (pipeline/effects.py).
export type EffectsParams = {
  brightness: number; // -1..1, 0 = unchanged
  contrast: number; // -1..1, 0 = unchanged
  saturation: number; // 0..2, 1 = unchanged
  sharpen: number; // 0..1, 0 = unchanged
};

export const DEFAULT_EFFECTS_PARAMS: EffectsParams = {
  brightness: 0,
  contrast: 0,
  saturation: 1,
  sharpen: 0,
};

export type SaveVersionParams = StretchParams &
  EffectsParams & {
    note: string;
    fix_halos: boolean;
    // Stacking params that produced the currently loaded master -- recorded
    // alongside the stretch settings so the note's "what changed" is meaningful
    // across iterations, not just the display stretch.
    sigma?: number;
    apply_dark?: boolean;
    apply_flat?: boolean;
    integration_method?: IntegrationMethod;
    // Non-destructive crop/rotate applied on top of the linear master.
    rotation: number;
    crop_x?: number;
    crop_y?: number;
    crop_width?: number;
    crop_height?: number;
  };

export type VersionStats = {
  snr_db: number | null;
};

export type Version = {
  id: string;
  workspace_id: string;
  note: string;
  params: SaveVersionParams;
  stats: VersionStats;
  created_at: string;
};

export type MasterDimensions = {
  width: number;
  height: number;
};

export type ExportFormat = "tiff" | "png" | "jpeg";

export type ExportParams = StretchParams &
  EffectsParams & {
    fix_halos: boolean;
    rotation: number;
    crop_x?: number;
    crop_y?: number;
    crop_width?: number;
    crop_height?: number;
    format: ExportFormat;
    destination_path: string;
  };
