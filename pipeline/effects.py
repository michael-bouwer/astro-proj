"""Simple display-space post-processing adjustments (brightness, contrast,
saturation, vibrance, star reduction, noise reduction, sharpen), applied last
-- after stretch and halo-fix -- to whatever's about to be shown or written
out. Same non-destructive philosophy as stretch.py/halos.py: never touches
the linear master.

Generic over dtype (uint8 preview, uint16 save/export) the same way
halos.fix_star_halos is, via np.iinfo(img.dtype).max rather than assuming
8-bit.
"""
import cv2
import numpy as np

from . import color


def _to_float01(img):
    max_val = np.iinfo(img.dtype).max
    return img.astype(np.float32) / max_val, max_val, img.dtype


def _from_float01(img_f32, max_val, dtype):
    return np.clip(img_f32 * max_val, 0, max_val).astype(dtype)


def adjust_brightness(img, amount):
    """amount in [-1, 1]; additive offset in normalized display space."""
    if not amount:
        return img
    normalized, max_val, dtype = _to_float01(img)
    return _from_float01(normalized + amount, max_val, dtype)


def adjust_contrast(img, amount):
    """amount in [-1, 1]; linear stretch around the midpoint (0.5)."""
    if not amount:
        return img
    normalized, max_val, dtype = _to_float01(img)
    factor = 1.0 + amount
    return _from_float01((normalized - 0.5) * factor + 0.5, max_val, dtype)


def adjust_saturation(img, amount):
    """amount is a multiplier: 1.0 = unchanged, 0 = grayscale, >1 = more saturated."""
    if amount == 1.0:
        return img
    normalized, max_val, dtype = _to_float01(img)
    hsv = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * amount, 0.0, 1.0)
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return _from_float01(np.clip(result, 0.0, 1.0), max_val, dtype)


def adjust_vibrance(img, amount):
    """amount in [-1, 1]; like saturation, but scales its own effect down as
    a pixel's existing saturation rises -- muted background/nebula color gets
    lifted while already-vivid star cores are largely left alone, rather than
    saturation's flat multiplier pushing both equally (and clipping the
    vivid ones first). Zero effect at both ends of the saturation range (grey
    has nothing to boost; fully saturated has nothing left to protect), peak
    effect at moderate saturation.
    """
    if not amount:
        return img
    normalized, max_val, dtype = _to_float01(img)
    hsv = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    hsv[:, :, 1] = np.clip(sat + amount * sat * (1.0 - sat), 0.0, 1.0)
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return _from_float01(np.clip(result, 0.0, 1.0), max_val, dtype)


def reduce_stars(img, amount, star_mask=None):
    """amount in [0, 1]; shrinks bloated star profiles so fainter stars and
    nebula detail aren't crowded out by oversized cores.

    Erodes the star mask by a fixed amount to find the "shrink zone" -- the
    ring of pixels that were part of a star but the eroded, smaller mask no
    longer covers -- then blends *that* zone toward a locally blurred
    estimate, same mechanism halos.fix_star_halos uses for its ring fill,
    just anchored to an eroded rather than dilated boundary. `amount` scales
    how strongly that zone gets pulled toward the blur rather than changing
    the erosion itself, so the slider response stays smooth instead of
    jumping between discrete erosion steps.
    """
    if not amount or star_mask is None:
        return img
    normalized, max_val, dtype = _to_float01(img)

    mask_u8 = (star_mask * 255).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(mask_u8, kernel, iterations=3)

    shrink_zone = cv2.subtract(mask_u8, eroded)
    shrink_alpha = cv2.GaussianBlur(shrink_zone, (7, 7), 0).astype(np.float32) / 255.0 * amount
    fill = cv2.GaussianBlur(normalized, (15, 15), 0)

    result = normalized * (1 - shrink_alpha[:, :, np.newaxis]) + fill * shrink_alpha[:, :, np.newaxis]
    return _from_float01(np.clip(result, 0.0, 1.0), max_val, dtype)


def reduce_noise(img, amount, star_mask=None):
    """amount in [0, 1]; edge-preserving smoothing, blended in more strongly
    over background than over stars, so grain gets cleaned up without
    softening star cores or fine nebula/wisp detail.

    A bilateral filter is already edge-aware on its own (it only smooths
    where neighboring pixels are close in value, so it naturally backs off at
    sharp star edges); star_mask -- see color.star_mask, computed once on the
    already-processed display image -- adds an extra, explicit layer of
    protection specifically for stars on top of that.
    """
    if not amount:
        return img
    normalized, max_val, dtype = _to_float01(img)
    smoothed = cv2.bilateralFilter(normalized, d=9, sigmaColor=0.08, sigmaSpace=7)

    if star_mask is not None:
        protect = cv2.GaussianBlur(star_mask, (9, 9), 0)[:, :, np.newaxis]
        smoothed = normalized * protect + smoothed * (1 - protect)

    result = normalized * (1 - amount) + smoothed * amount
    return _from_float01(np.clip(result, 0.0, 1.0), max_val, dtype)


def sharpen(img, amount):
    """amount in [0, 1]; unsharp mask strength."""
    if not amount:
        return img
    normalized, max_val, dtype = _to_float01(img)
    blurred = cv2.GaussianBlur(normalized, (0, 0), sigmaX=2.0)
    sharpened = normalized + amount * (normalized - blurred)
    return _from_float01(np.clip(sharpened, 0.0, 1.0), max_val, dtype)


def apply(
    img,
    brightness=0.0,
    contrast=0.0,
    saturation=1.0,
    vibrance=0.0,
    star_reduction=0.0,
    noise_reduction=0.0,
    sharpen_amount=0.0,
):
    result = adjust_brightness(img, brightness)
    result = adjust_contrast(result, contrast)
    result = adjust_vibrance(result, vibrance)
    result = adjust_saturation(result, saturation)

    if star_reduction or noise_reduction:
        # Computed once, on the already tone/color-adjusted image, and shared
        # by both -- star_mask's own cost (a percentile over the whole frame)
        # isn't worth paying twice.
        normalized_for_mask, _, _ = _to_float01(result)
        mask = color.star_mask(normalized_for_mask)
        result = reduce_stars(result, star_reduction, star_mask=mask)
        result = reduce_noise(result, noise_reduction, star_mask=mask)

    result = sharpen(result, sharpen_amount)
    return result
