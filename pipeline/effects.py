"""Simple display-space post-processing adjustments (brightness, contrast,
saturation, sharpen), applied last -- after stretch and halo-fix -- to
whatever's about to be shown or written out. Same non-destructive philosophy
as stretch.py/halos.py: never touches the linear master.

Generic over dtype (uint8 preview, uint16 save/export) the same way
halos.fix_star_halos is, via np.iinfo(img.dtype).max rather than assuming
8-bit.
"""
import cv2
import numpy as np


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


def sharpen(img, amount):
    """amount in [0, 1]; unsharp mask strength."""
    if not amount:
        return img
    normalized, max_val, dtype = _to_float01(img)
    blurred = cv2.GaussianBlur(normalized, (0, 0), sigmaX=2.0)
    sharpened = normalized + amount * (normalized - blurred)
    return _from_float01(np.clip(sharpened, 0.0, 1.0), max_val, dtype)


def apply(img, brightness=0.0, contrast=0.0, saturation=1.0, sharpen_amount=0.0):
    result = adjust_brightness(img, brightness)
    result = adjust_contrast(result, contrast)
    result = adjust_saturation(result, saturation)
    result = sharpen(result, sharpen_amount)
    return result
