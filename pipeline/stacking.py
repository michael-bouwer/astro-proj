"""Disk-backed frame stacking with outlier-rejecting combine algorithms.

Frame arrays for a full session (dozens of 16-bit multi-megapixel frames) don't
reliably fit in RAM, so the stack is built on a memory-mapped temp file and
combined a horizontal chunk (row band) at a time.

Two rejection algorithms are offered, going beyond a plain "average with a
sigma threshold":

  - sigma_clip_combine: iterative, median/MAD-based (robust) sigma clipping.
    Centering on the median with a robust spread estimate (rather than mean/
    std, which the outliers themselves skew) and refining across a few passes
    catches hot pixels / cosmic rays / satellite trails that a single mean/std
    pass can miss when one bad value is enough to inflate std past the point
    of rejecting anything.
  - winsorized_sigma_clip_combine: estimates a robust std by "winsorizing"
    (capping, not discarding) outliers over a few passes, then does one real
    rejection pass against that estimate -- a different, complementary way of
    getting a std estimate the outliers themselves can't skew.

Both accept an optional per-frame `weights` array (see compute_frame_weights)
so a frame's measured quality controls how much it contributes to the final
average -- a weight of 0 excludes a frame from the output without needing to
physically remove it from the memmap.
"""
import gc
import os
import tempfile
import warnings

import numpy as np


def create_memmap_stack(count, height, width, channels=3):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_filepath = temp_file.name
    temp_file.close()
    mem_stack = np.memmap(
        temp_filepath, dtype=np.float32, mode="w+", shape=(count, height, width, channels)
    )
    return mem_stack, temp_filepath


def create_coverage_stack(count, height, width):
    """A (count, height, width) boolean memmap paralleling create_memmap_stack's
    pixel data, marking which pixels in each frame are real (aligned) data vs.
    the black border fill introduced by rotating/shifting a frame to match the
    reference -- see alignment.ReferenceFrame.align. Passed to the combine
    functions below as valid_mask_stack so that border fill never counts
    toward a pixel's average.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_filepath = temp_file.name
    temp_file.close()
    coverage_stack = np.memmap(temp_filepath, dtype=bool, mode="w+", shape=(count, height, width))
    return coverage_stack, temp_filepath


def cleanup_memmap(mem_stack, temp_filepath):
    """Windows-safe teardown: flush, release the file lock, then delete the temp file."""
    mem_stack.flush()
    if hasattr(mem_stack, "base") and hasattr(mem_stack.base, "close"):
        mem_stack.base.close()
    del mem_stack
    gc.collect()
    try:
        os.remove(temp_filepath)
    except PermissionError:
        pass  # OS will reclaim it once the last handle closes


def compute_frame_weights(qualities, reject_sigma=3.0):
    """Turns per-frame quality scores (SNR in dB, e.g. from color.estimate_snr;
    None where it couldn't be measured) into a (weights, kept) pair for the
    combine functions below.

    Frames whose quality is a statistical outlier (more than reject_sigma
    robust-sigma below the *measured* frames' median) are excluded -- the
    same median/MAD "outlier relative to the population" idea
    sigma_clip_combine uses per pixel, applied once per frame to the frame's
    own quality instead. Median/MAD rather than mean/std for the same reason
    as the pixel-level rejection: with only a handful of frames, one bad
    frame can skew a plain mean/std enough that it no longer looks like an
    outlier by its own (now-skewed) measure. Survivors get a weight
    proportional to their SNR on a linear scale (dB is logarithmic;
    weighting should track actual signal quality, not its log), normalized
    so the average kept weight is 1.0 -- that keeps the overall exposure
    level of the combine the same as an unweighted average would give when
    every frame is roughly equal quality.

    Frames with no measurable quality (None -- e.g. no usable star/background
    split) are never rejected on quality and get the mean weight of the
    frames that could be measured, since there's nothing to judge them
    against.
    """
    n = len(qualities)
    scores = np.array([q if q is not None else np.nan for q in qualities], dtype=np.float64)
    measured = scores[~np.isnan(scores)]

    if measured.size < 2:
        # Not enough measured frames to judge outliers.
        return np.ones(n, dtype=np.float32), np.ones(n, dtype=bool)

    median = np.median(measured)
    madn = 1.4826 * np.median(np.abs(measured - median))
    mean = measured.mean()  # weighting scale below still uses the plain mean

    if madn == 0:
        # No measurable spread among the measured frames -- nothing to judge outliers against.
        return np.ones(n, dtype=np.float32), np.ones(n, dtype=bool)

    kept = np.isnan(scores) | (scores >= median - reject_sigma * madn)

    linear = np.where(np.isnan(scores), 10 ** (mean / 20), 10 ** (scores / 20))
    weights = np.where(kept, linear, 0.0).astype(np.float32)
    kept_mean = weights[kept].mean() if kept.any() else 0.0
    if kept_mean > 0:
        weights = weights / kept_mean

    return weights, kept


def _masked_median(values, valid):
    """Median along axis 0, counting only positions where `valid` is True --
    equivalent to np.nanmedian(np.where(valid, values, np.nan), axis=0) but
    dramatically faster. np.nanmedian's generic implementation doesn't have
    the fast vectorized path np.sort/np.mean/np.std do -- at real image
    sizes (multi-megapixel frames, dozens of subs) that difference alone was
    the entire cost of a stacking run (measured ~14x on a single chunk: 9.4s
    vs 0.66s, confirmed bit-identical output). Sorting each pixel's frame
    values (which does have a fast path) with invalid entries pushed past
    the end, then picking the middle of the *valid* run via a per-pixel
    count, computes the exact same value.

    A pixel with zero valid frames (e.g. outside every frame's coverage after
    alignment) has nothing to take a middle of -- returns 0 there rather than
    the pushed sentinel (+inf), which would otherwise propagate into inf/nan
    through any further arithmetic on the result.
    """
    n = values.shape[0]
    pushed = np.where(valid, values, np.inf)
    sorted_vals = np.sort(pushed, axis=0)
    counts = valid.sum(axis=0)
    lower_idx = np.clip((counts - 1) // 2, 0, n - 1)
    upper_idx = np.clip(counts // 2, 0, n - 1)
    lower_val = np.take_along_axis(sorted_vals, lower_idx[np.newaxis, ...], axis=0)[0]
    upper_val = np.take_along_axis(sorted_vals, upper_idx[np.newaxis, ...], axis=0)[0]
    return np.where(counts > 0, (lower_val + upper_val) / 2.0, 0.0)


def _valid_chunk(valid_mask_stack, frame_count, y, y_end, shape):
    """Pulls a (frame_count, rows, width) coverage slice off valid_mask_stack
    and broadcasts it to a chunk's (frames, rows, width, channels) shape --
    or, with no coverage tracking, everything is valid.
    """
    if valid_mask_stack is None:
        return np.ones(shape, dtype=bool)
    coverage = np.array(valid_mask_stack[:frame_count, y:y_end, :])
    return np.broadcast_to(coverage[..., np.newaxis], shape)


def _weighted_average(values, keep, weights):
    """sum(value * weight) / sum(weight) over axis 0, restricted to `keep`,
    never dividing by zero (falls back to keeping everything for a pixel
    where `keep` would otherwise leave nothing)."""
    would_empty = ~keep.any(axis=0)
    keep = keep | would_empty[np.newaxis, ...]

    w = weights.reshape(-1, *([1] * (values.ndim - 1)))
    filled = np.where(keep, values, 0.0)
    weighted_sum = (filled * w).sum(axis=0)
    weight_total = (keep * w).sum(axis=0)
    return weighted_sum / np.maximum(weight_total, 1e-6)


def sigma_clip_combine(
    mem_stack, frame_count, sigma=3.0, iterations=3, weights=None, chunk_rows=100, progress_cb=None, valid_mask_stack=None
):
    """Iterative, median/MAD-based (robust) sigma-clipped weighted average.

    Rejection statistics (the median/MAD each pass) are computed on the raw
    pixel values, not weighted -- weighting reflects how much a frame should
    count toward the final image, not how "typical" a value is for outlier
    purposes. Weights only enter at the final averaging step.

    valid_mask_stack (see create_coverage_stack) excludes each frame's
    black border-fill pixels (introduced by rotating/shifting to align with
    the reference) from the outset, so a frame that doesn't reach a given
    edge pixel never counts toward that pixel's statistics or average --
    without this, a pixel with partial frame coverage gets its value dragged
    toward black in proportion to how many frames don't reach it.
    """
    _, height, width, channels = mem_stack.shape
    result = np.zeros((height, width, channels), dtype=np.float32)
    weights = np.ones(frame_count, dtype=np.float32) if weights is None else weights

    for y in range(0, height, chunk_rows):
        y_end = min(y + chunk_rows, height)
        chunk = np.array(mem_stack[:frame_count, y:y_end, :, :])  # pull off disk into RAM
        valid = _valid_chunk(valid_mask_stack, frame_count, y, y_end, chunk.shape)  # narrows as iterations reject more

        for _ in range(iterations):
            median = _masked_median(chunk, valid)
            madn = 1.4826 * _masked_median(np.abs(chunk - median), valid)  # robust std estimate
            lower = median - sigma * madn
            upper = median + sigma * madn
            reject_now = valid & ((chunk < lower) | (chunk > upper))

            still_kept = valid & ~reject_now
            would_empty = still_kept.sum(axis=0) == 0
            reject_now = reject_now & ~would_empty[np.newaxis, ...]

            valid = valid & ~reject_now

        result[y:y_end, :, :] = _weighted_average(chunk, valid, weights)

        if progress_cb:
            progress_cb((y_end / height) * 100.0)

    return result


def winsorized_sigma_clip_combine(
    mem_stack, frame_count, sigma=3.0, winsorize_iterations=3, weights=None, chunk_rows=100, progress_cb=None, valid_mask_stack=None
):
    """Winsorized Sigma Clipping: winsorizes (caps, doesn't discard) values
    outside the current mean/std over a few passes to get a std estimate
    that isn't itself skewed by the outliers it's meant to reject, then does
    one real rejection pass against that robust estimate.

    Seeded from a robust median/MAD estimate rather than the raw mean/std:
    with a small frame count, a single extreme outlier can inflate the raw
    std enough that even the first winsorizing pass's bounds stay wide
    enough to never actually cap it, which stalls every later iteration at
    that same contaminated starting point.

    valid_mask_stack -- see sigma_clip_combine's docstring -- excludes each
    frame's black border-fill pixels from every statistic computed here
    (median/MAD seed, winsorized mean/std, and the final average), via NaN
    (mean/std already have numpy's fast nan-aware path, unlike median).
    """
    _, height, width, channels = mem_stack.shape
    result = np.zeros((height, width, channels), dtype=np.float32)
    weights = np.ones(frame_count, dtype=np.float32) if weights is None else weights

    for y in range(0, height, chunk_rows):
        y_end = min(y + chunk_rows, height)
        chunk = np.array(mem_stack[:frame_count, y:y_end, :, :])
        valid = _valid_chunk(valid_mask_stack, frame_count, y, y_end, chunk.shape)
        nan_chunk = np.where(valid, chunk, np.nan)

        median = _masked_median(chunk, valid)
        mean, std = median, 1.4826 * _masked_median(np.abs(chunk - median), valid)
        with warnings.catch_warnings():
            # Pixels with zero coverage from any frame (nan_chunk all-NaN
            # there) trigger numpy's "empty slice" warnings below -- benign,
            # since _weighted_average's own would_empty fallback handles
            # those pixels correctly regardless of what mean/std come out to.
            warnings.simplefilter("ignore", category=RuntimeWarning)
            for _ in range(winsorize_iterations):
                lower = mean - sigma * std
                upper = mean + sigma * std
                winsorized = np.clip(nan_chunk, lower, upper)
                mean = np.nanmean(winsorized, axis=0)
                std = np.nanstd(winsorized, axis=0) * 1.134  # bias correction for the variance winsorizing removes

        lower = mean - sigma * std
        upper = mean + sigma * std
        keep = valid & (chunk >= lower) & (chunk <= upper)

        result[y:y_end, :, :] = _weighted_average(chunk, keep, weights)

        if progress_cb:
            progress_cb((y_end / height) * 100.0)

    return result


def median_combine(mem_stack, frame_count, chunk_rows=100, progress_cb=None, valid_mask_stack=None):
    """Plain median combine -- cheaper and still useful for small calibration-frame
    sets. Unlike the two rejection-based combines above, this isn't weighted:
    a weighted median isn't a standard feature of the tools this pipeline is
    modeled on, so per-frame quality only affects the sigma-clip methods.

    valid_mask_stack -- see sigma_clip_combine's docstring -- excludes each
    frame's black border-fill pixels from the median.
    """
    _, height, width, channels = mem_stack.shape
    result = np.zeros((height, width, channels), dtype=np.float32)

    for y in range(0, height, chunk_rows):
        y_end = min(y + chunk_rows, height)
        chunk = np.array(mem_stack[:frame_count, y:y_end, :, :])
        if valid_mask_stack is None:
            result[y:y_end, :, :] = np.median(chunk, axis=0)
        else:
            valid = _valid_chunk(valid_mask_stack, frame_count, y, y_end, chunk.shape)
            result[y:y_end, :, :] = _masked_median(chunk, valid)
        if progress_cb:
            progress_cb((y_end / height) * 100.0)

    return result
