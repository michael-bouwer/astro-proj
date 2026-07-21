import type { CropRect } from "../api/types";

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Largest rect of the given pixel aspect ratio (width/height), centered in a
 * frameWidth x frameHeight frame. Returned as 0-1 fractions of the frame, the
 * same coordinate space CropRect uses everywhere else. */
export function centeredCropForAspect(aspect: number, frameWidth: number, frameHeight: number): CropRect {
  const frameAspect = frameWidth / frameHeight;

  let width: number;
  let height: number;
  if (aspect > frameAspect) {
    width = 1;
    height = (frameAspect / aspect) * 1;
  } else {
    height = 1;
    width = (aspect / frameAspect) * 1;
  }

  return {
    x: (1 - width) / 2,
    y: (1 - height) / 2,
    width,
    height,
  };
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
