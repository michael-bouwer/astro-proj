"""Background neutralization and star color calibration on linear (unstretched) data.

Split out of the original apply_beautiful_stretch() so the stacked master stays
linear -- stretching is a display concern (stretch.py), calibration is a data
concern, and mixing them meant the saved master could never be re-stretched
without re-running the whole pipeline.
"""
import cv2
import numpy as np


def star_mask(bgr_f32, percentile=99.5):
    """Binary mask (1.0 = star, 0.0 = sky) used to separate signal from background.

    Uses a manual >= comparison rather than cv2.threshold: when many star pixels
    share the same (e.g. saturated) value, the percentile can land exactly on the
    image max, and cv2.threshold's strict '>' would then exclude every pixel.
    """
    gray = cv2.cvtColor(bgr_f32, cv2.COLOR_BGR2GRAY)
    cutoff = np.percentile(gray, percentile)
    return (gray >= cutoff).astype(np.float32)


def neutralize_background(bgr_f32, mask=None):
    """Equalizes each channel's sky background to the dimmest channel's level,
    removing light-pollution color cast without destroying the background's
    overall brightness floor.

    Subtracting each channel's full background median down to zero (the
    original approach) leaves nothing but noise in the background for a
    subsequent auto-stretch to work with -- auto-stretch already computes its
    own robust black point from the data's natural distribution, so zeroing
    the background here doubly-destroys it: about half the background pixels
    end up clipped to exactly 0, and the stretch has only noise left to lift,
    which shows up as color speckle/gradient artifacts once stretched.
    """
    if mask is None:
        mask = star_mask(bgr_f32)

    result = bgr_f32.copy()
    sky_pixels = result[mask == 0.0]
    bg = np.median(sky_pixels, axis=0)  # (B, G, R)
    offset = bg - bg.min()  # each channel's excess over the dimmest channel

    result[:, :, 0] -= offset[0]
    result[:, :, 1] -= offset[1]
    result[:, :, 2] -= offset[2]
    return np.clip(result, 0.0, None)


def calibrate_star_color(bgr_f32, mask=None):
    """Scales R and B channels so the mean star color matches G (removes color cast in stars)."""
    if mask is None:
        mask = star_mask(bgr_f32)

    result = bgr_f32.copy()
    mean_b = np.mean(result[:, :, 0][mask == 1.0])
    mean_g = np.mean(result[:, :, 1][mask == 1.0])
    mean_r = np.mean(result[:, :, 2][mask == 1.0])

    result[:, :, 0] *= mean_g / max(mean_b, 1e-5)
    result[:, :, 2] *= mean_g / max(mean_r, 1e-5)
    return result


def calibrate(bgr_f32):
    """Runs star color calibration followed by background neutralization.

    Background neutralization must run last: it's a uniform per-channel shift,
    so if star color calibration ran afterward, its star-derived R/B scale
    factors would get applied to the just-neutralized background too and
    reintroduce a color cast there.
    """
    mask = star_mask(bgr_f32)
    star_calibrated = calibrate_star_color(bgr_f32, mask)
    mask = star_mask(star_calibrated)
    return neutralize_background(star_calibrated, mask)


def estimate_snr(bgr_f32, mask=None):
    """Rough signal-to-noise estimate in dB: mean star-pixel signal vs. background
    noise (std of sky pixels). Not a rigorous photometric SNR, just a cheap, honest
    number for comparing stacks (e.g. across a sigma threshold or frame count change).
    Returns None if there's no usable background/star split to measure against.
    """
    if mask is None:
        mask = star_mask(bgr_f32)

    star_pixels = bgr_f32[mask == 1.0]
    sky_pixels = bgr_f32[mask == 0.0]
    if star_pixels.size == 0 or sky_pixels.size == 0:
        return None

    signal = float(star_pixels.mean())
    noise = float(sky_pixels.std())
    if noise <= 0 or signal <= 0:
        return None

    return 20 * np.log10(signal / noise)
