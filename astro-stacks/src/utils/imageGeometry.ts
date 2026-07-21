import type { CropRect } from "../api/types";

export const FULL_FRAME_CROP: CropRect = { x: 0, y: 0, width: 1, height: 1 };

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Largest rect of the given pixel aspect ratio (width/height) that fits
 * inside `baseRect`, centered on `baseRect`'s own center -- reorients a crop
 * in place rather than resetting to the full frame, so clicking a preset
 * after manually cropping reshapes the existing crop instead of discarding
 * it. Pass FULL_FRAME_CROP as `baseRect` for the "no crop yet" case. Returned
 * as 0-1 fractions of the frameWidth x frameHeight frame, the same coordinate
 * space CropRect uses everywhere else. */
export function centeredCropForAspect(aspect: number, baseRect: CropRect, frameWidth: number, frameHeight: number): CropRect {
  const basePixelWidth = baseRect.width * frameWidth;
  const basePixelHeight = baseRect.height * frameHeight;
  const baseAspect = basePixelWidth / basePixelHeight;

  let widthPx: number;
  let heightPx: number;
  if (aspect > baseAspect) {
    widthPx = basePixelWidth;
    heightPx = widthPx / aspect;
  } else {
    heightPx = basePixelHeight;
    widthPx = heightPx * aspect;
  }
  const width = widthPx / frameWidth;
  const height = heightPx / frameHeight;

  const centerX = baseRect.x + baseRect.width / 2;
  const centerY = baseRect.y + baseRect.height / 2;

  return {
    x: clamp(centerX - width / 2, 0, 1 - width),
    y: clamp(centerY - height / 2, 0, 1 - height),
    width,
    height,
  };
}

/** True if a crop's pixel aspect ratio matches `aspect` within a small
 * tolerance -- used to highlight the active preset button and to detect when
 * a manual drag has deviated from it. */
export function cropMatchesAspect(crop: CropRect, aspect: number, frameWidth: number, frameHeight: number): boolean {
  const cropAspect = (crop.width * frameWidth) / (crop.height * frameHeight);
  return Math.abs(cropAspect - aspect) < 0.005;
}

/** Exact targetWidth x targetHeight pixel rect centered on `baseRect`'s own
 * center (same "reorient in place" behavior as centeredCropForAspect) --
 * used by the fixed-resolution presets (1080p, 4K, ...) rather than
 * aspect-only ones. Caller is expected to only offer a target size that fits
 * within the frame (see the presets' own width/height disabled check). */
export function centeredCropForSize(
  targetWidth: number,
  targetHeight: number,
  baseRect: CropRect,
  frameWidth: number,
  frameHeight: number,
): CropRect {
  const width = clamp(targetWidth / frameWidth, 0, 1);
  const height = clamp(targetHeight / frameHeight, 0, 1);
  const centerX = baseRect.x + baseRect.width / 2;
  const centerY = baseRect.y + baseRect.height / 2;

  return {
    x: clamp(centerX - width / 2, 0, 1 - width),
    y: clamp(centerY - height / 2, 0, 1 - height),
    width,
    height,
  };
}

/** True if a crop's pixel dimensions match targetWidth x targetHeight within
 * a fraction of a pixel -- used to highlight the active resolution preset. */
export function cropMatchesSize(
  crop: CropRect,
  targetWidth: number,
  targetHeight: number,
  frameWidth: number,
  frameHeight: number,
): boolean {
  return Math.abs(crop.width * frameWidth - targetWidth) < 1 && Math.abs(crop.height * frameHeight - targetHeight) < 1;
}

/** Simplifies a pixel width/height into a small-integer ratio label like "3:2",
 * falling back to a decimal ratio if no clean small-integer match is found. */
export function simplifyRatio(width: number, height: number): string {
  const gcd = (a: number, b: number): number => (b === 0 ? a : gcd(b, a % b));
  const divisor = gcd(Math.round(width), Math.round(height));
  if (divisor > 0) {
    const w = Math.round(width) / divisor;
    const h = Math.round(height) / divisor;
    if (w <= 50 && h <= 50) return `${w}:${h}`;
  }
  return `${(width / height).toFixed(2)}:1`;
}
