"""Bias / dark / flat master-frame calibration.

Standard formula (bias signal is present in every exposure, including darks):
    normalized_flat = (master_flat - master_bias) / mean(master_flat - master_bias)
    calibrated_light = (light - master_dark) / normalized_flat

Any of the three calibration frame sets may be missing; each step is skipped
and calibration degrades gracefully rather than failing.
"""
import os

import numpy as np

from . import raw_io
from .stacking import cleanup_memmap, create_memmap_stack, median_combine


def _require_same_shape(a_shape, b_shape, a_label, b_label):
    if a_shape != b_shape:
        raise ValueError(
            f"{a_label} shape {a_shape} doesn't match {b_label} shape {b_shape}. "
            "This usually means the frames were shot in different camera orientations "
            "(portrait vs landscape) or come from different cameras/crop settings."
        )


def build_master_frame(frame_paths, progress_cb=None):
    """Median-combines a set of calibration frames (bias/dark/flat) into one master.

    Calibration sets are usually small (tens of frames), but frames themselves
    can still be large, so this reuses the same disk-backed combine as light
    stacking rather than assuming everything fits in RAM.
    """
    if not frame_paths:
        return None

    first = raw_io.load_frame(frame_paths[0])
    height, width, channels = first.shape

    mem_stack, temp_filepath = create_memmap_stack(len(frame_paths), height, width, channels)
    mem_stack[0] = first
    try:
        for i, path in enumerate(frame_paths[1:], start=1):
            frame = raw_io.load_frame(path)
            _require_same_shape(frame.shape, first.shape, os.path.basename(path), os.path.basename(frame_paths[0]))
            mem_stack[i] = frame

        master = median_combine(mem_stack, len(frame_paths), progress_cb=progress_cb)
    finally:
        cleanup_memmap(mem_stack, temp_filepath)

    return master


def normalize_flat(master_flat, master_bias=None, min_relative_floor=0.05):
    if master_bias is not None:
        _require_same_shape(master_flat.shape, master_bias.shape, "master flat", "master bias")
        flat = master_flat - master_bias
    else:
        flat = master_flat.copy()

    # Per-channel mean, not a single scalar over R+G+B combined: each channel has its
    # own vignetting shape and absolute brightness (e.g. a saturated/overexposed blue
    # channel sits at a totally different level than red/green). Normalizing every
    # channel against one shared global mean lets whichever channel is brightest skew
    # the other channels' correction, which shows up as a spatially-varying color cast.
    mean = flat.mean(axis=(0, 1), keepdims=True)
    # Floor near-zero/negative corners (extreme vignetting, dust, dead pixels) at a
    # fraction of each channel's own mean rather than an absolute constant: flat pixel
    # values are ~1e4-1e5, so an absolute floor like 1e-3 is effectively zero relative
    # to that scale. Dividing light frames by a near-zero normalized_flat later
    # (calibrate_light) would amplify those pixels by orders of magnitude.
    floor = np.maximum(mean * min_relative_floor, 1e-6)
    flat = np.clip(flat, floor, None)
    return flat / mean


def calibrate_light(light, master_bias=None, master_dark=None, normalized_flat=None):
    calibrated = light.copy()

    if master_dark is not None:
        _require_same_shape(light.shape, master_dark.shape, "light frame", "master dark")
        calibrated -= master_dark
    elif master_bias is not None:
        _require_same_shape(light.shape, master_bias.shape, "light frame", "master bias")
        calibrated -= master_bias

    if normalized_flat is not None:
        _require_same_shape(light.shape, normalized_flat.shape, "light frame", "master flat")
        calibrated /= normalized_flat

    return np.clip(calibrated, 0.0, None)
