/** Angle in degrees from a pivot point to a pointer position, standard screen
 * coordinates (y grows downward), 0deg pointing right, increasing clockwise. */
export function angleFromCenter(centerX: number, centerY: number, pointX: number, pointY: number): number {
  return (Math.atan2(pointY - centerY, pointX - centerX) * 180) / Math.PI;
}

/** Wraps a raw angle difference into (-180, 180] so a full-circle drag doesn't
 * jump discontinuously when atan2 crosses the +/-180 boundary. */
export function normalizeAngleDelta(delta: number): number {
  let wrapped = delta % 360;
  if (wrapped > 180) wrapped -= 360;
  if (wrapped <= -180) wrapped += 360;
  return wrapped;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
