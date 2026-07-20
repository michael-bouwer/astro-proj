"""Nonlinear display stretches, applied on demand -- never baked into the saved master.

Three options:
  - auto: PixInsight/Siril-style auto-stretch. Black point and midtone are derived
    from the image's own median/MAD rather than a fixed constant, so it looks
    reasonable regardless of how dim the underlying linear signal is. This is the
    default for a reason: a fixed midtone (e.g. "0.25") only looks right for the
    specific signal level it was tuned against -- too weak and the preview reads
    as black, too strong and it's blown out. Default method for /preview.
  - mtf: manual midtone transfer function, single midtone parameter, for
    fine-tuning once you're past the initial "does this look like anything" step.
  - asinh: compresses bright star cores less aggressively than MTF/log, which is
    why the original React slider was built around it.
"""
import numpy as np


def _normalize(bgr_f32):
    max_val = np.max(bgr_f32)
    return bgr_f32 / max_val if max_val > 0 else bgr_f32


def _mtf(x, midtone):
    m = midtone
    return ((m - 1) * x) / (((2 * m - 1) * x) - m)


def midtone_transfer_function(bgr_f32, midtone=0.25):
    """c in (0, 1); lower = more aggressive stretch of shadows/midtones."""
    normalized = _normalize(bgr_f32)
    return np.clip(_mtf(normalized, midtone), 0.0, 1.0)


def _solve_midtone(x, target):
    """Inverse of _mtf: the midtone m such that _mtf(x, m) == target."""
    denom = (2 * x * target) - target - x
    if x <= 0 or abs(denom) < 1e-12:
        return 0.5
    return float(np.clip(x * (target - 1) / denom, 1e-6, 1.0))


def auto_stretch(bgr_f32, target_bkg=0.25, shadow_clip=-2.8):
    """Derives black point + midtone from the image's own median/MAD (linked
    across channels, so the color calibration already applied isn't disturbed),
    then applies the standard MTF curve. Matches PixInsight's ScreenTransferFunction
    auto-stretch / Siril's autostretch algorithm.
    """
    normalized = _normalize(bgr_f32)
    median = float(np.median(normalized))
    madn = 1.4826 * float(np.median(np.abs(normalized - median)))  # robust std-dev estimate

    # madn == 0 means the background has no measurable spread (e.g. synthetic/flat
    # test data) -- clipping the black point to the median in that case would zero
    # out the entire background instead of just the noise floor, so skip the clip.
    black_point = np.clip(median + shadow_clip * madn, 0.0, median) if madn > 0 else 0.0
    midtone = _solve_midtone(median - black_point, target_bkg)

    clipped = np.clip((normalized - black_point) / max(1.0 - black_point, 1e-6), 0.0, 1.0)
    return np.clip(_mtf(clipped, midtone), 0.0, 1.0)


def asinh_stretch(bgr_f32, scale=1000.0):
    normalized = _normalize(bgr_f32)
    stretched = np.arcsinh(normalized * scale) / np.arcsinh(scale)
    return np.clip(stretched, 0.0, 1.0)


def _stretched(bgr_f32, method, midtone, scale, target_bkg, shadow_clip):
    if method == "asinh":
        return asinh_stretch(bgr_f32, scale)
    if method == "mtf":
        return midtone_transfer_function(bgr_f32, midtone)
    return auto_stretch(bgr_f32, target_bkg, shadow_clip)


def to_uint8(bgr_f32, method="auto", midtone=0.25, scale=1000.0, target_bkg=0.25, shadow_clip=-2.8):
    stretched = _stretched(bgr_f32, method, midtone, scale, target_bkg, shadow_clip)
    return (stretched * 255).astype(np.uint8)


def to_uint16(bgr_f32, method="auto", midtone=0.25, scale=1000.0, target_bkg=0.25, shadow_clip=-2.8):
    stretched = _stretched(bgr_f32, method, midtone, scale, target_bkg, shadow_clip)
    return (stretched * 65535).astype(np.uint16)
