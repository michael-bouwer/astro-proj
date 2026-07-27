"""Ties calibration, alignment, and stacking together into one pipeline run.

Produces a linear, background/color-calibrated master (`master_linear.npy`,
loadable with raw_io.load_linear_master). No stretch is applied here -- see
stretch.py for that, applied on demand at preview/export time.
"""
import os

from . import calibration, color, raw_io
from .alignment import ReferenceFrame
from .stacking import (
    check_temp_space,
    cleanup_memmap,
    compute_frame_weights,
    create_coverage_stack,
    create_memmap_stack,
    median_combine,
    memory_warning,
    sigma_clip_combine,
    stack_bytes_required,
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

# Pixel stride for the per-frame SNR used to weight/reject frames (see
# color.estimate_snr). Every frame's quality must be measured the same way to
# be comparable, so the reference frame and the aligned frames share this.
# The SNR reported for the finished master is deliberately measured at full
# resolution instead -- that one is a headline number, not a relative ranking.
#
# Measured on a real 10 MP master: subsample=1 costs 230ms/frame (38.9s of
# pure overhead across a 134-frame stack) vs 19ms/frame at subsample=4 -- a
# 12x cut for a 0.02 dB difference in the measured value, well inside the
# noise of the quality-weighting decision it feeds.
SNR_SUBSAMPLE = 4


def _noop(stage, percent, message):
    pass


def _clip_warning(kind, master_frame, source_files):
    """source_files is the set the master was built from -- its first entry
    tells us the white level to compare against (an 8-bit source saturates at
    255, not the 16-bit ceiling raw files use). See raw_io.white_level_for."""
    clipped = calibration.clipped_channels(master_frame, clip_level=raw_io.white_level_for(source_files[0]))
    if not clipped:
        return None
    channels = "/".join(clipped)
    plural = "s" if len(clipped) > 1 else ""
    return (
        f"Master {kind} frame is saturated in the {channels} channel{plural} -- its real "
        f"vignette/signal can't be measured there, so calibration can't correct that "
        f"channel. Reshoot {kind}s at a lower exposure/gain so no channel clips."
    )


def build_calibration_masters(dataset_dir, output_dir=None, progress_cb=None):
    """output_dir, if given, doubles as a cache: a master bias/dark/flat is
    only actually rebuilt (median-combining every raw frame in that set, the
    expensive part) if the corresponding source folder's contents have
    changed since the last run -- re-stacking the same dataset repeatedly, or
    across integration-method/sigma experiments, doesn't pay that cost again.
    """
    progress_cb = progress_cb or _noop
    warnings = []
    cache_dir = os.path.join(output_dir, calibration.CACHE_DIRNAME) if output_dir else None

    bias_files = raw_io.list_frames(os.path.join(dataset_dir, "biases"))
    dark_files = raw_io.list_frames(os.path.join(dataset_dir, "darks"))
    flat_files = raw_io.list_frames(os.path.join(dataset_dir, "flats"))

    def build_or_reuse(kind, files, step_pct):
        if not files:
            return None
        if cache_dir:
            signature = calibration.calibration_signature(files)
            cached = calibration.load_cached_master(cache_dir, kind, signature)
            if cached is not None:
                progress_cb("calibration", step_pct, f"Reusing cached master {kind} ({len(files)} frames)...")
                return cached
        progress_cb("calibration", step_pct, f"Building master {kind} ({len(files)} frames)...")
        master = calibration.build_master_frame(files)
        if cache_dir:
            calibration.save_cached_master(cache_dir, kind, signature, master)
        return master

    master_bias = build_or_reuse("bias", bias_files, 0)
    if master_bias is not None:
        warning = _clip_warning("bias", master_bias, bias_files)
        if warning:
            warnings.append(warning)

    master_dark = build_or_reuse("dark", dark_files, 33)
    if master_dark is not None:
        warning = _clip_warning("dark", master_dark, dark_files)
        if warning:
            warnings.append(warning)

    master_flat = build_or_reuse("flat", flat_files, 66)
    if master_flat is not None:
        warning = _clip_warning("flat", master_flat, flat_files)
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
    excluded_frames=None,
    progress_cb=None,
):
    """Runs the full lights pipeline for a dataset directory and saves the linear master.

    dataset_dir is expected to contain a lights/ subdirectory, and optionally
    darks/, flats/, biases/ for calibration. Output (master_linear.npy) is written
    to output_dir if given, otherwise dataset_dir -- workspaces write into their own
    directory so source frame folders (which may be referenced in place, not owned
    by this app) are never modified.

    excluded_frames -- basenames the caller wants skipped entirely (a manual
    override on top of the automatic quality rejection below; see
    workspace.load_excluded_frames) -- never even get decoded/aligned.
    """
    progress_cb = progress_cb or _noop
    output_dir = output_dir or dataset_dir
    if integration_method not in INTEGRATION_METHODS:
        raise ValueError(f"integration_method must be one of {INTEGRATION_METHODS}, got {integration_method!r}")

    excluded_frames = set(excluded_frames or ())
    all_light_files = raw_io.list_frames(os.path.join(dataset_dir, "lights"))
    light_files = [path for path in all_light_files if os.path.basename(path) not in excluded_frames]
    if len(light_files) < 2:
        raise ValueError("Need at least 2 light frames to stack.")

    need_calibration_masters = apply_dark or apply_flat
    master_bias = master_dark = normalized_flat = None
    calibration_warnings = []
    if need_calibration_masters:
        built_bias, built_dark, built_flat, calibration_warnings = build_calibration_masters(
            dataset_dir, output_dir=output_dir, progress_cb=progress_cb
        )
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

    # Checked before allocating anything, and before the expensive
    # decode/align loop below -- running out of scratch space two thirds of the
    # way through a long session is a miserable way to find out. The reference
    # frame has to be decoded first only because that's what establishes the
    # frame dimensions this estimate needs.
    required_bytes = stack_bytes_required(len(light_files), height, width, 3)
    check_temp_space(required_bytes)
    # A soft, informational counterpart to the hard check above: unlike disk
    # space, the OS can generally absorb a tight RAM footprint via its own
    # paging (a real 210-frame session ran to completion at 99% system
    # memory, released cleanly right after), so this only ever warns, never
    # blocks. See stacking.memory_warning.
    resource_warnings = []
    ram_note = memory_warning(required_bytes)
    if ram_note:
        resource_warnings.append(ram_note)

    mem_stack, temp_filepath = create_memmap_stack(len(light_files), height, width, 3)
    coverage_stack, coverage_temp_filepath = create_coverage_stack(len(light_files), height, width)
    mem_stack[0] = reference.bgr
    coverage_stack[0] = True  # the reference frame is never warped, so it's valid everywhere
    successful = 1
    # Per-frame SNR (dB), parallel to the frames actually written into
    # mem_stack -- feeds compute_frame_weights below so a frame's measured
    # quality controls how much it counts toward the combine. successful_filenames
    # tracks the same frames by name, in the same order, for frame_quality below.
    # The reference frame is never warped, so it has no border fill to exclude
    # -- but it must be measured with the same stride as the aligned frames
    # below or its quality isn't comparable to theirs.
    qualities = [color.estimate_snr(reference.bgr, subsample=SNR_SUBSAMPLE)]
    successful_filenames = [os.path.basename(light_files[reference_index])]
    # (basename, status, error) for frames that never made it into the stack.
    # Registration genuinely failing is a different thing from the frame
    # blowing up while being read or calibrated (corrupt file, unreadable
    # disk, ...), and the frame-review UI is a lot more useful when it can say
    # which happened -- and what the error actually was.
    failed_frames = []

    try:
        remaining = light_files[:reference_index] + light_files[reference_index + 1 :]
        for idx, path in enumerate(remaining, start=1):
            try:
                frame = calibrate(raw_io.load_frame(path))
                result = reference.align(frame)
                if result is None:
                    failed_frames.append((os.path.basename(path), "failed_to_align", None))
                    continue
                aligned, valid_mask = result
                mem_stack[successful] = aligned
                coverage_stack[successful] = valid_mask
                # valid_mask matters here, not just for the combine: without it
                # the warped frame's black border fill counts as sky and
                # inflates the noise estimate, so a frame that merely needed a
                # larger shift looks lower-quality than it is and gets
                # under-weighted (or rejected) below. See color.estimate_snr.
                qualities.append(color.estimate_snr(aligned, coverage=valid_mask, subsample=SNR_SUBSAMPLE))
                successful_filenames.append(os.path.basename(path))
                successful += 1
            except Exception as exc:
                failed_frames.append((os.path.basename(path), "error", f"{type(exc).__name__}: {exc}"))
                continue
            progress_cb("aligning", (idx / len(remaining)) * 100, f"Aligned frame {idx}/{len(remaining)}")

        if successful < 2:
            raise RuntimeError(f"Only {successful} frame(s) aligned successfully; need at least 2.")

        weights, kept = compute_frame_weights(qualities, reject_sigma=QUALITY_REJECT_SIGMA)
        quality_rejected_count = int((~kept).sum())

        # Per-frame outcome for every light frame this run considered (or was
        # told to skip) -- feeds the frame-review UI. successful_filenames,
        # qualities, and kept are all built/indexed in lockstep above.
        frame_quality = [
            {"filename": filename, "status": "included" if is_kept else "quality_rejected", "snr_db": quality, "error": None}
            for filename, quality, is_kept in zip(successful_filenames, qualities, kept.tolist())
        ]
        frame_quality += [
            {"filename": filename, "status": status, "snr_db": None, "error": error}
            for filename, status, error in failed_frames
        ]
        all_basenames = {os.path.basename(path) for path in all_light_files}
        frame_quality += [
            {"filename": filename, "status": "manually_excluded", "snr_db": None, "error": None}
            for filename in sorted(excluded_frames)
            if filename in all_basenames
        ]
        frame_quality.sort(key=lambda entry: entry["filename"])

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
        "resource_warnings": resource_warnings,
        "frame_quality": frame_quality,
    }
