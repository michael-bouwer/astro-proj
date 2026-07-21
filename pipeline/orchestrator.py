"""Ties calibration, alignment, and stacking together into one pipeline run.

Produces a linear, background/color-calibrated master (`master_linear.npy`,
loadable with raw_io.load_linear_master). No stretch is applied here -- see
stretch.py for that, applied on demand at preview/export time.
"""
import os

from . import calibration, color, raw_io
from .alignment import ReferenceFrame
from .stacking import (
    cleanup_memmap,
    compute_frame_weights,
    create_coverage_stack,
    create_memmap_stack,
    median_combine,
    sigma_clip_combine,
    winsorized_sigma_clip_combine,
)

LINEAR_MASTER_FILENAME = "master_linear.npy"

INTEGRATION_METHODS = ("sigma_clip", "winsorized_sigma_clip", "median")

# Frames whose measured SNR is a statistical outlier relative to the rest of
# the session get excluded from the combine (weight 0) -- see
# stacking.compute_frame_weights. Not user-configurable: this is a quality
# safety net, not a creative parameter, matching how other stacking tools
# apply their own frame-quality rejection by default.
QUALITY_REJECT_SIGMA = 3.0


def _noop(stage, percent, message):
    pass


def _clip_warning(kind, master_frame):
    clipped = calibration.clipped_channels(master_frame)
    if not clipped:
        return None
    channels = "/".join(clipped)
    plural = "s" if len(clipped) > 1 else ""
    return (
        f"Master {kind} frame is saturated in the {channels} channel{plural} -- its real "
        f"vignette/signal can't be measured there, so calibration can't correct that "
        f"channel. Reshoot {kind}s at a lower exposure/gain so no channel clips."
    )


def build_calibration_masters(dataset_dir, progress_cb=None):
    progress_cb = progress_cb or _noop
    warnings = []

    bias_files = raw_io.list_frames(os.path.join(dataset_dir, "biases"))
    dark_files = raw_io.list_frames(os.path.join(dataset_dir, "darks"))
    flat_files = raw_io.list_frames(os.path.join(dataset_dir, "flats"))

    progress_cb("calibration", 0, f"Building master bias ({len(bias_files)} frames)...")
    master_bias = calibration.build_master_frame(bias_files) if bias_files else None
    if master_bias is not None:
        warning = _clip_warning("bias", master_bias)
        if warning:
            warnings.append(warning)

    progress_cb("calibration", 33, f"Building master dark ({len(dark_files)} frames)...")
    master_dark = calibration.build_master_frame(dark_files) if dark_files else None
    if master_dark is not None:
        warning = _clip_warning("dark", master_dark)
        if warning:
            warnings.append(warning)

    progress_cb("calibration", 66, f"Building master flat ({len(flat_files)} frames)...")
    master_flat = calibration.build_master_frame(flat_files) if flat_files else None
    if master_flat is not None:
        warning = _clip_warning("flat", master_flat)
        if warning:
            warnings.append(warning)
    normalized_flat = calibration.normalize_flat(master_flat, master_bias) if master_flat is not None else None

    progress_cb("calibration", 100, "Calibration masters ready.")
    return master_bias, master_dark, normalized_flat, warnings


def run_pipeline(
    dataset_dir,
    output_dir=None,
    sigma=3.0,
    apply_dark=True,
    apply_flat=True,
    integration_method="sigma_clip",
    progress_cb=None,
):
    """Runs the full lights pipeline for a dataset directory and saves the linear master.

    dataset_dir is expected to contain a lights/ subdirectory, and optionally
    darks/, flats/, biases/ for calibration. Output (master_linear.npy) is written
    to output_dir if given, otherwise dataset_dir -- workspaces write into their own
    directory so source frame folders (which may be referenced in place, not owned
    by this app) are never modified.
    """
    progress_cb = progress_cb or _noop
    output_dir = output_dir or dataset_dir
    if integration_method not in INTEGRATION_METHODS:
        raise ValueError(f"integration_method must be one of {INTEGRATION_METHODS}, got {integration_method!r}")

    light_files = raw_io.list_frames(os.path.join(dataset_dir, "lights"))
    if len(light_files) < 2:
        raise ValueError("Need at least 2 light frames to stack.")

    need_calibration_masters = apply_dark or apply_flat
    master_bias = master_dark = normalized_flat = None
    calibration_warnings = []
    if need_calibration_masters:
        built_bias, built_dark, built_flat, calibration_warnings = build_calibration_masters(dataset_dir, progress_cb)
        master_bias = built_bias
        master_dark = built_dark if apply_dark else None
        normalized_flat = built_flat if apply_flat else None

    def calibrate(frame):
        if not need_calibration_masters:
            return frame
        return calibration.calibrate_light(frame, master_bias, master_dark, normalized_flat)

    # The middle file (by name, which for a single capture session is also
    # chronological order) rather than the first: every other frame gets
    # warped to match whichever frame is picked here, so the total rotation/
    # shift that needs correcting -- and therefore how much of the frame the
    # final stack loses to coverage gaps -- is minimized by picking from the
    # middle of the session instead of an end. This matters most when a
    # session was actually shot in two sittings with the rig repositioned in
    # between: the first file could easily land in the smaller of the two
    # groups, forcing the majority of frames through the larger of the two
    # corrections instead of the minority.
    reference_index = len(light_files) // 2
    progress_cb("reference", 0, "Loading reference frame...")
    reference = ReferenceFrame(calibrate(raw_io.load_frame(light_files[reference_index])))
    height, width = reference.height, reference.width

    mem_stack, temp_filepath = create_memmap_stack(len(light_files), height, width, 3)
    coverage_stack, coverage_temp_filepath = create_coverage_stack(len(light_files), height, width)
    mem_stack[0] = reference.bgr
    coverage_stack[0] = True  # the reference frame is never warped, so it's valid everywhere
    successful = 1
    # Per-frame SNR (dB), parallel to the frames actually written into
    # mem_stack -- feeds compute_frame_weights below so a frame's measured
    # quality controls how much it counts toward the combine.
    qualities = [color.estimate_snr(reference.bgr)]

    try:
        remaining = light_files[:reference_index] + light_files[reference_index + 1 :]
        for idx, path in enumerate(remaining, start=1):
            try:
                frame = calibrate(raw_io.load_frame(path))
                result = reference.align(frame)
                if result is None:
                    continue
                aligned, valid_mask = result
                mem_stack[successful] = aligned
                coverage_stack[successful] = valid_mask
                qualities.append(color.estimate_snr(aligned))
                successful += 1
            except Exception:
                continue
            progress_cb("aligning", (idx / len(remaining)) * 100, f"Aligned frame {idx}/{len(remaining)}")

        if successful < 2:
            raise RuntimeError(f"Only {successful} frame(s) aligned successfully; need at least 2.")

        weights, kept = compute_frame_weights(qualities, reject_sigma=QUALITY_REJECT_SIGMA)
        quality_rejected_count = int((~kept).sum())

        progress_cb("stacking", 0, f"Stacking {successful} frames ({integration_method})...")
        if integration_method == "sigma_clip":
            combine = sigma_clip_combine
            combine_kwargs = {"sigma": sigma, "weights": weights}
        elif integration_method == "winsorized_sigma_clip":
            combine = winsorized_sigma_clip_combine
            combine_kwargs = {"sigma": sigma, "weights": weights}
        else:
            combine = median_combine
            combine_kwargs = {}
        combined = combine(
            mem_stack,
            successful,
            progress_cb=lambda pct: progress_cb("stacking", pct, "Stacking..."),
            valid_mask_stack=coverage_stack,
            **combine_kwargs,
        )
    finally:
        cleanup_memmap(mem_stack, temp_filepath)
        cleanup_memmap(coverage_stack, coverage_temp_filepath)

    progress_cb("color", 0, "Calibrating star color and neutralizing background...")
    linear_master = color.calibrate(combined)
    snr_db = color.estimate_snr(linear_master)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, LINEAR_MASTER_FILENAME)
    raw_io.save_linear_master(output_path, linear_master)
    progress_cb("done", 100, "Pipeline complete.")

    return {
        "output_path": output_path,
        "light_frame_count": len(light_files),
        "stacked_frame_count": successful - quality_rejected_count,
        "rejected_frame_count": len(light_files) - successful,
        "quality_rejected_count": quality_rejected_count,
        "applied_dark": apply_dark and master_dark is not None,
        "applied_flat": apply_flat and normalized_flat is not None,
        "integration_method": integration_method,
        "snr_db": snr_db,
        "width": width,
        "height": height,
        "calibration_warnings": calibration_warnings,
    }
