"""Nonlinear display stretches, applied on demand -- never baked into the saved master.

Three options:
  - auto: black point and midtone are derived from the image's own median/MAD
    rather than a fixed constant, so it looks reasonable regardless of how dim
    the underlying linear signal is. This is the default for a reason: a fixed
    midtone (e.g. "0.25") only looks right for the specific signal level it
    was tuned against -- too weak and the preview reads as black, too strong
    and it's blown out. Default method for /preview.
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
    then applies the standard MTF curve.
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


def compute_histogram(bgr_f32, bins=256, shadow_clip=-2.8):
    """Per-channel (B, G, R) histogram of the linear data -- what
    target_bkg/shadow_clip actually operate on, so the Stretch tab can show
    where a setting lands relative to the real data instead of tuning blind.
    Downsampled for speed, since the overall shape is what matters here, not
    an exact per-pixel count. Counts are log1p-compressed: a small handful of
    bright star pixels next to a huge background peak would otherwise round
    to an invisible bar on a linear count axis.

    Also returns the black point "auto" stretch would currently compute from
    this same data (on the same absolute scale as display_max below), so the
    frontend can mark exactly where that method's shadow clip lands.
    """
    flat = bgr_f32[::4, ::4, :] if bgr_f32.size > 4_000_000 else bgr_f32
    display_max = float(np.percentile(flat, 99.5))
    if display_max <= 0:
        display_max = float(np.max(flat)) or 1.0

    channels = {}
    for i, name in enumerate(("b", "g", "r")):
        channel_data = np.clip(flat[:, :, i], 0, display_max)
        counts, _ = np.histogram(channel_data, bins=bins, range=(0, display_max))
        channels[name] = np.log1p(counts).tolist()

    true_max = float(np.max(bgr_f32))
    normalized = _normalize(bgr_f32)
    median = float(np.median(normalized))
    madn = 1.4826 * float(np.median(np.abs(normalized - median)))
    black_point_normalized = float(np.clip(median + shadow_clip * madn, 0.0, median)) if madn > 0 else 0.0
    black_point = black_point_normalized * true_max

    return {"display_max": display_max, "bins": bins, "black_point": black_point, **channels}


def to_uint8(bgr_f32, method="auto", midtone=0.25, scale=1000.0, target_bkg=0.25, shadow_clip=-2.8):
    stretched = _stretched(bgr_f32, method, midtone, scale, target_bkg, shadow_clip)
    return (stretched * 255).astype(np.uint8)


def to_uint16(bgr_f32, method="auto", midtone=0.25, scale=1000.0, target_bkg=0.25, shadow_clip=-2.8):
    stretched = _stretched(bgr_f32, method, midtone, scale, target_bkg, shadow_clip)
    return (stretched * 65535).astype(np.uint16)
