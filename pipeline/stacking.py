"""Disk-backed frame stacking with sigma-clipped rejection.

Frame arrays for a full session (dozens of 16-bit multi-megapixel frames) don't
reliably fit in RAM, so the stack is built on a memory-mapped temp file and
combined a horizontal chunk (row band) at a time -- the same strategy the
original script used for plain median stacking, generalized here to sigma
clipping so hot pixels, satellite trails, and cosmic-ray hits get rejected
per-pixel instead of only damped by the median.
"""
import gc
import os
import tempfile

import numpy as np


def create_memmap_stack(count, height, width, channels=3):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_filepath = temp_file.name
    temp_file.close()
    mem_stack = np.memmap(
        temp_filepath, dtype=np.float32, mode="w+", shape=(count, height, width, channels)
    )
    return mem_stack, temp_filepath


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


def sigma_clip_combine(mem_stack, frame_count, sigma=3.0, chunk_rows=100, progress_cb=None):
    """Per-pixel sigma-clipped mean across the frame axis, chunked to bound RAM use.

    Falls back to including every frame for a pixel if clipping would reject all
    of them (e.g. a frame count too low for the statistics to be meaningful).
    """
    _, height, width, channels = mem_stack.shape
    result = np.zeros((height, width, channels), dtype=np.float32)

    for y in range(0, height, chunk_rows):
        y_end = min(y + chunk_rows, height)
        chunk = np.array(mem_stack[:frame_count, y:y_end, :, :])  # pull off disk into RAM

        mean = chunk.mean(axis=0)
        std = chunk.std(axis=0)
        lower = mean - sigma * std
        upper = mean + sigma * std
        keep = (chunk >= lower) & (chunk <= upper)

        kept_counts = keep.sum(axis=0)
        keep = np.where(kept_counts[np.newaxis, ...] == 0, True, keep)

        summed = np.where(keep, chunk, 0).sum(axis=0)
        divisor = np.maximum(keep.sum(axis=0), 1)
        result[y:y_end, :, :] = summed / divisor

        if progress_cb:
            progress_cb((y_end / height) * 100.0)

    return result


def median_combine(mem_stack, frame_count, chunk_rows=100, progress_cb=None):
    """Plain median combine -- cheaper and still useful for small calibration-frame sets."""
    _, height, width, channels = mem_stack.shape
    result = np.zeros((height, width, channels), dtype=np.float32)

    for y in range(0, height, chunk_rows):
        y_end = min(y + chunk_rows, height)
        chunk = np.array(mem_stack[:frame_count, y:y_end, :, :])
        result[y:y_end, :, :] = np.median(chunk, axis=0)
        if progress_cb:
            progress_cb((y_end / height) * 100.0)

    return result
