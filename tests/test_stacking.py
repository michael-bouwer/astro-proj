import numpy as np
import pytest

from pipeline.stacking import (
    compute_frame_weights,
    median_combine,
    sigma_clip_combine,
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
