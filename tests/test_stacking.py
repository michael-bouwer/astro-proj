import os
import numpy as np
import pytest

from pipeline import stacking
from pipeline.stacking import (
    COMBINE_MEMORY_BUDGET_BYTES,
    MAX_CHUNK_ROWS,
    STACK_TEMP_DIR_ENV,
    _auto_chunk_rows,
    check_temp_space,
    compute_frame_weights,
    median_combine,
    memory_warning,
    sigma_clip_combine,
    stack_bytes_required,
    stack_temp_dir,
    winsorized_sigma_clip_combine,
)


def _stack(values):
    """Turns a flat list of per-frame pixel values into a (N, 1, 1, 1) mem_stack-shaped array."""
    return np.array(values, dtype=np.float32).reshape(len(values), 1, 1, 1)


def _coverage(valid_flags):
    """Turns a flat list of per-frame booleans into a (N, 1, 1) valid_mask_stack-shaped array."""
    return np.array(valid_flags, dtype=bool).reshape(len(valid_flags), 1, 1)


def test_sigma_clip_combine_rejects_outliers_that_mean_std_would_miss():
    # 6 frames at one pixel: 4 clean values tightly clustered around 1000,
    # 2 "bad" frames (e.g. a satellite trail hitting the same pixel in two
    # subs) at 5000. A plain mean/std single pass sees its own std inflated
    # by those two outliers (mean=2334, std=1886 here), which widens the
    # clip bounds enough that NEITHER outlier gets flagged -- the exact
    # failure mode robust (median/MAD) rejection exists to fix.
    mem_stack = _stack([1000, 1010, 990, 1005, 5000, 5000])
    result = sigma_clip_combine(mem_stack, 6, sigma=3.0)
    assert result[0, 0, 0] == pytest.approx(1001.25, abs=1.0)  # mean of the 4 clean values


def test_sigma_clip_combine_never_rejects_every_frame_for_a_pixel():
    # An unreasonably tight sigma would otherwise flag both points (each is
    # far from the median relative to the tiny band) -- the "never reject
    # everything" fallback should keep both rather than divide by zero.
    mem_stack = _stack([100, 900])
    result = sigma_clip_combine(mem_stack, 2, sigma=0.01)
    assert result[0, 0, 0] == pytest.approx(500.0)


def test_sigma_clip_combine_applies_frame_weights():
    # No real outlier here (all three values are close), so this isolates
    # the weighting step from the rejection step: zeroing the third frame's
    # weight should pull the result toward the first two only.
    mem_stack = _stack([1000, 1010, 1020])
    weights = np.array([1.0, 1.0, 0.0], dtype=np.float32)
    result = sigma_clip_combine(mem_stack, 3, sigma=3.0, weights=weights)
    assert result[0, 0, 0] == pytest.approx(1005.0)


def test_sigma_clip_combine_preserves_shape_and_dtype():
    rng = np.random.default_rng(7)
    mem_stack = rng.normal(1000, 20, (5, 10, 12, 3)).astype(np.float32)
    result = sigma_clip_combine(mem_stack, 5)
    assert result.shape == (10, 12, 3)
    assert result.dtype == np.float32


def test_winsorized_sigma_clip_combine_rejects_a_single_extreme_outlier():
    # 7 clean frames around 1000 plus one extreme outlier at 8000 -- a more
    # realistic single-bad-frame scenario (unlike the 2-of-6 case above,
    # which is a heavier contamination fraction than sigma-clip-family
    # methods are expected to handle).
    mem_stack = _stack([1000, 1005, 995, 1010, 990, 1002, 998, 8000])
    result = winsorized_sigma_clip_combine(mem_stack, 8, sigma=3.0)
    assert result[0, 0, 0] < 1100  # anchored to the clean cluster, not dragged up by the outlier


def test_winsorized_sigma_clip_combine_applies_frame_weights():
    mem_stack = _stack([1000, 1010, 1020])
    weights = np.array([1.0, 1.0, 0.0], dtype=np.float32)
    result = winsorized_sigma_clip_combine(mem_stack, 3, sigma=3.0, weights=weights)
    assert result[0, 0, 0] == pytest.approx(1005.0)


def test_winsorized_sigma_clip_combine_preserves_shape_and_dtype():
    rng = np.random.default_rng(8)
    mem_stack = rng.normal(1000, 20, (5, 10, 12, 3)).astype(np.float32)
    result = winsorized_sigma_clip_combine(mem_stack, 5)
    assert result.shape == (10, 12, 3)
    assert result.dtype == np.float32


def test_median_combine_basic():
    mem_stack = _stack([10, 20, 30])
    result = median_combine(mem_stack, 3)
    assert result[0, 0, 0] == 20.0


def test_compute_frame_weights_rejects_a_quality_outlier():
    # One frame far below the rest (e.g. a cloud-affected sub) should be
    # excluded entirely (weight 0, kept False); the rest keep a positive weight.
    qualities = [20.0, 21.0, 19.5, 20.5, -5.0]
    weights, kept = compute_frame_weights(qualities, reject_sigma=3.0)
    assert kept.tolist() == [True, True, True, True, False]
    assert weights[-1] == 0.0
    assert (weights[:-1] > 0).all()


def test_compute_frame_weights_keeps_everyone_when_too_few_measured():
    qualities = [20.0, None, None]
    weights, kept = compute_frame_weights(qualities)
    assert kept.all()
    assert (weights == 1.0).all()


def test_compute_frame_weights_unmeasured_frames_are_never_rejected():
    qualities = [20.0, 20.5, 19.5, 20.2, None]
    weights, kept = compute_frame_weights(qualities, reject_sigma=3.0)
    assert kept[-1]  # the unmeasurable frame is never flagged as an outlier
    assert weights[-1] > 0


def test_compute_frame_weights_weight_scales_with_linear_snr():
    # A frame measured at +6dB has roughly double the linear SNR of one at
    # 0dB (20*log10(2) ~= 6.02) -- weighting should track that linear scale,
    # not the dB value directly. Three distinct values (rather than a
    # repeated one) so the robust MAD estimate isn't degenerately zero.
    qualities = [0.0, 1.0, 6.0]
    weights, kept = compute_frame_weights(qualities, reject_sigma=3.0)
    assert kept.all()
    assert weights[2] == pytest.approx(weights[0] * 2, rel=0.05)


def test_sigma_clip_combine_excludes_invalid_coverage_from_average():
    # 3 clean frames around 1000, plus 2 frames whose warp didn't reach this
    # pixel (border-fill 0, marked invalid) -- without coverage exclusion the
    # two 0s would drag the average down; with it, the result should reflect
    # only the 3 real frames.
    mem_stack = _stack([1000, 1010, 990, 0, 0])
    valid = _coverage([True, True, True, False, False])
    result = sigma_clip_combine(mem_stack, 5, sigma=3.0, valid_mask_stack=valid)
    assert result[0, 0, 0] == pytest.approx(1000.0, abs=1.0)


def test_sigma_clip_combine_all_invalid_pixel_stays_zero_without_warning(recwarn):
    mem_stack = _stack([0, 0, 0])
    valid = _coverage([False, False, False])
    result = sigma_clip_combine(mem_stack, 3, sigma=3.0, valid_mask_stack=valid)
    assert result[0, 0, 0] == 0.0
    assert not any(issubclass(w.category, RuntimeWarning) for w in recwarn.list)


def test_winsorized_sigma_clip_combine_excludes_invalid_coverage_from_average():
    mem_stack = _stack([1000, 1010, 990, 1005, 0, 0])
    valid = _coverage([True, True, True, True, False, False])
    result = winsorized_sigma_clip_combine(mem_stack, 6, sigma=3.0, valid_mask_stack=valid)
    assert result[0, 0, 0] == pytest.approx(1001.25, abs=1.0)


def test_winsorized_sigma_clip_combine_all_invalid_pixel_stays_zero_without_warning(recwarn):
    mem_stack = _stack([0, 0, 0])
    valid = _coverage([False, False, False])
    result = winsorized_sigma_clip_combine(mem_stack, 3, sigma=3.0, valid_mask_stack=valid)
    assert result[0, 0, 0] == 0.0
    assert not any(issubclass(w.category, RuntimeWarning) for w in recwarn.list)


def test_median_combine_excludes_invalid_coverage_from_median():
    mem_stack = _stack([10, 20, 30, 0])
    valid = _coverage([True, True, True, False])
    result = median_combine(mem_stack, 4, valid_mask_stack=valid)
    assert result[0, 0, 0] == 20.0  # median of [10, 20, 30], not [10, 20, 30, 0]


# --- adaptive chunk sizing -------------------------------------------------


def test_auto_chunk_rows_shrinks_as_frame_count_grows():
    """The whole point: peak memory used to scale with frame count because
    chunk_rows was fixed. More frames must now mean proportionally fewer rows."""
    wide = 3908
    rows = [_auto_chunk_rows(n, wide, 3) for n in (20, 60, 134, 210)]
    assert rows == sorted(rows, reverse=True)
    assert rows[0] > rows[-1]


def test_auto_chunk_rows_holds_the_memory_budget_across_frame_counts():
    wide = 3908
    for frames in (20, 60, 134, 210, 500):
        rows = _auto_chunk_rows(frames, wide, 3)
        projected_peak = rows * frames * wide * 3 * 4 * stacking.CHUNK_MEMORY_OVERHEAD
        # Only the clamp at MAX_CHUNK_ROWS may undershoot the budget; never overshoot.
        assert projected_peak <= COMBINE_MEMORY_BUDGET_BYTES or rows == MAX_CHUNK_ROWS


def test_auto_chunk_rows_never_returns_less_than_one_row():
    # A pathologically wide frame with a huge stack still has to make progress.
    assert _auto_chunk_rows(2000, 20000, 3, budget_bytes=1024) == 1


def test_auto_chunk_rows_is_capped_for_small_stacks():
    assert _auto_chunk_rows(2, 64, 3) == MAX_CHUNK_ROWS


@pytest.mark.parametrize(
    "combine",
    [
        lambda stack, n, rows: sigma_clip_combine(stack, n, sigma=2.0, chunk_rows=rows),
        lambda stack, n, rows: winsorized_sigma_clip_combine(stack, n, sigma=2.0, chunk_rows=rows),
        lambda stack, n, rows: median_combine(stack, n, chunk_rows=rows),
    ],
    ids=["sigma_clip", "winsorized", "median"],
)
def test_chunking_does_not_change_the_result(combine):
    """Chunking only splits the work into row bands; each pixel is still
    combined across frames only. Auto-sizing chunks therefore has to be
    bit-identical to any fixed chunk_rows, or it isn't a safe optimisation."""
    rng = np.random.default_rng(7)
    mem_stack = (rng.normal(1000, 50, (9, 37, 11, 3))).astype(np.float32)
    mem_stack[3, 5, 5] = 9e4  # an outlier for the rejection paths to bite on

    baseline = combine(mem_stack, 9, 100)
    for rows in (1, 7, 37, 1000, None):
        assert np.array_equal(combine(mem_stack, 9, rows), baseline)


# --- scratch space ---------------------------------------------------------


def test_stack_bytes_required_counts_pixel_data_and_coverage():
    # 4 bytes per float32 channel sample, plus 1 byte per pixel of coverage.
    assert stack_bytes_required(10, 100, 200, 3) == 10 * 100 * 200 * 3 * 4 + 10 * 100 * 200


def test_stack_temp_dir_prefers_explicit_then_env_then_system(tmp_path, monkeypatch):
    monkeypatch.delenv(STACK_TEMP_DIR_ENV, raising=False)
    system_default = stack_temp_dir()
    assert system_default  # whatever tempfile.gettempdir() gives

    monkeypatch.setenv(STACK_TEMP_DIR_ENV, str(tmp_path / "from_env"))
    assert stack_temp_dir() == str(tmp_path / "from_env")
    # An explicit argument still wins over the environment override.
    assert stack_temp_dir(str(tmp_path / "explicit")) == str(tmp_path / "explicit")


def test_check_temp_space_passes_when_space_is_available(tmp_path):
    check_temp_space(1024, temp_dir=str(tmp_path))  # must not raise


def test_check_temp_space_raises_naming_the_env_var_and_the_shortfall(tmp_path):
    with pytest.raises(RuntimeError) as excinfo:
        check_temp_space(500 * 10**12, temp_dir=str(tmp_path))  # 500 TB

    message = str(excinfo.value)
    assert STACK_TEMP_DIR_ENV in message  # tells the user how to redirect it
    assert str(tmp_path) in message  # and which directory fell short
    assert "GB" in message


def test_check_temp_space_creates_a_missing_temp_dir(tmp_path):
    target = tmp_path / "does" / "not" / "exist"
    check_temp_space(1024, temp_dir=str(target))
    assert target.is_dir()


def test_memmap_stacks_are_created_in_the_env_var_directory(tmp_path, monkeypatch):
    """The redirect is only useful if the actual scratch files land there --
    these are the multi-GB ones, so it's the whole point of the override."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv(STACK_TEMP_DIR_ENV, str(scratch))

    mem_stack, mem_path = stacking.create_memmap_stack(2, 8, 8, 3)
    coverage, coverage_path = stacking.create_coverage_stack(2, 8, 8)
    try:
        assert os.path.dirname(mem_path) == str(scratch)
        assert os.path.dirname(coverage_path) == str(scratch)
    finally:
        stacking.cleanup_memmap(mem_stack, mem_path)
        stacking.cleanup_memmap(coverage, coverage_path)


# --- memory_warning ---------------------------------------------------------


def _gb(n):
    # Decimal GB, matching memory_warning's own /1e9 formatting -- 1024**3
    # (GiB) would drift from the message's rendered figures.
    return int(n * 1e9)


def test_memory_warning_returns_none_comfortably_under_the_threshold():
    # 1 GB required against 100 GB of RAM -- nowhere close to the 50% default.
    assert memory_warning(_gb(1), total_ram_bytes=_gb(100)) is None


def test_memory_warning_returns_a_message_over_the_threshold():
    message = memory_warning(_gb(60), total_ram_bytes=_gb(100))
    assert message is not None
    assert "60.0 GB" in message
    assert "100.0 GB" in message


def test_memory_warning_is_exclusive_at_exactly_the_threshold():
    # Exactly at threshold * total must not warn ("comfortably under" includes
    # the boundary itself) -- only when required strictly exceeds it.
    assert memory_warning(_gb(50), total_ram_bytes=_gb(100), threshold=0.5) is None
    assert memory_warning(_gb(50) + 1, total_ram_bytes=_gb(100), threshold=0.5) is not None


def test_memory_warning_respects_a_custom_threshold():
    required = _gb(30)
    total = _gb(100)
    assert memory_warning(required, total_ram_bytes=total, threshold=0.5) is None
    assert memory_warning(required, total_ram_bytes=total, threshold=0.2) is not None


def test_memory_warning_defaults_to_the_real_machines_ram(monkeypatch):
    """No total_ram_bytes given -- must fall back to psutil, not silently no-op."""
    import psutil

    class _FakeVM:
        total = _gb(10)

    monkeypatch.setattr(psutil, "virtual_memory", lambda: _FakeVM())
    assert memory_warning(_gb(1)) is None  # 1 GB of 10 GB, under 50%
    assert memory_warning(_gb(9)) is not None  # 9 GB of 10 GB, over 50%


@pytest.mark.parametrize(
    "label, frames, height, width, total_ram_gb, expect_warning",
    [
        # Measured this session against the real Heart Nebula frame size
        # (3908x2602). Jellyfish (210 frames, 27.76 GB) on this machine's
        # 33.5 GB peaked at 99% RAM -- should warn. A small synthetic session
        # should not.
        ("real Jellyfish session on the machine it was measured on", 210, 2602, 3908, 33.5, True),
        ("small synthetic session", 4, 200, 260, 33.5, False),
    ],
)
def test_memory_warning_against_real_measured_sessions(label, frames, height, width, total_ram_gb, expect_warning):
    required = stack_bytes_required(frames, height, width, 3)
    result = memory_warning(required, total_ram_bytes=total_ram_gb * 1024**3)
    assert (result is not None) == expect_warning, label
