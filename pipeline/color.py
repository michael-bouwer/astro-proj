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


def defringe_star_edges(bgr_f32, mask=None, ring_size=10, max_desaturation=0.85, min_saturation=0.45, full_saturation=0.75):
    """Suppresses magenta/purple chromatic-aberration fringing in the ring
    around bright star cores by desaturating it, rather than shifting color
    channels directly.

    Real optics focus different wavelengths slightly differently, so a bright
    star's outer wings often carry a genuine (if usually subtle) magenta/
    purple color cast; a strong display stretch later turns that into a
    visibly sharp halo. The standard fix (matching what dedicated
    purple-fringe removal tools do) works in HSV space and touches only
    saturation, leaving brightness alone, and only within the actual magenta/
    purple hue band -- so real blue reflection-nebula color elsewhere in the
    frame is left untouched rather than desaturated along with it.

    Hue alone isn't a reliable enough gate on real data: a whole frame can
    carry a mild, genuine ambient purple/magenta cast (residual chromatic
    effects, imperfect color calibration) with a hue close enough to true
    fringing that hue-gating alone doesn't tell them apart -- it ends up
    desaturating a visible patch around every detected star, not just actual
    fringing. A saturation floor fixes that: only pixels clearly *more*
    saturated than the ambient level (i.e. actual concentrated color, not
    just the background's usual tint) are treated as fringing.

    Proximity, hue match, and saturation are all smoothly feathered (no hard
    edge -- see halos.fix_star_halos for what a hard mask boundary looks like
    once stretched) and the effect is capped short of full desaturation so a
    genuinely magenta star doesn't get flattened to grey.
    """
    if mask is None:
        mask = star_mask(bgr_f32)

    mask_u8 = (mask * 255).astype(np.uint8)
    kernel = np.ones((ring_size, ring_size), np.uint8)
    ring = cv2.dilate(mask_u8, kernel, iterations=3)
    proximity = cv2.GaussianBlur(ring, (21, 21), 0).astype(np.float32) / 255.0

    peak = np.max(bgr_f32)
    normalized = (bgr_f32 / peak if peak > 0 else bgr_f32).astype(np.float32)
    hsv = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
    hue, sat = hsv[:, :, 0], hsv[:, :, 1]

    # OpenCV's float32 HSV hue is in [0, 360); pure magenta sits at 300, with
    # chromatic-aberration fringing typically spanning a purple-to-pink band
    # either side of it. A soft cosine falloff from the band center rather
    # than a hard in/out cutoff keeps the hue gate itself from introducing a
    # visible edge.
    hue_distance = np.minimum(np.abs(hue - 300.0), 360.0 - np.abs(hue - 300.0))
    hue_gate = np.clip(1.0 - hue_distance / 45.0, 0.0, 1.0)
    sat_gate = np.clip((sat - min_saturation) / (full_saturation - min_saturation), 0.0, 1.0)

    alpha = proximity * hue_gate * sat_gate * max_desaturation
    hsv[:, :, 1] *= 1.0 - alpha

    result_normalized = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return result_normalized * peak


def calibrate(bgr_f32):
    """Runs star color calibration, near-star defringing, then background
    neutralization.

    Background neutralization must run last: it's a uniform per-channel shift,
    so if star color calibration ran afterward, its star-derived R/B scale
    factors would get applied to the just-neutralized background too and
    reintroduce a color cast there. Defringing runs in between, against the
    star-calibrated color balance, since it's a local correction on top of
    that global one.
    """
    mask = star_mask(bgr_f32)
    star_calibrated = calibrate_star_color(bgr_f32, mask)
    mask = star_mask(star_calibrated)
    defringed = defringe_star_edges(star_calibrated, mask)
    mask = star_mask(defringed)
    return neutralize_background(defringed, mask)


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
