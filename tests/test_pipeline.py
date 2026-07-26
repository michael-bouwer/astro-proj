import os
import time

import cv2
import numpy as np
import pytest

from pipeline import alignment, calibration, color, effects, halos, orchestrator, raw_io, stretch, transform
from tests.conftest import HEIGHT, WIDTH, make_bias_frame, make_dark_frame, make_flat_frame, make_light_frame, _rng


def test_calibrate_light_removes_dark_and_bias_signal():
    rng = _rng()
    dark = make_dark_frame(rng).astype(np.float32)
    light = make_light_frame(rng).astype(np.float32)

    calibrated = calibration.calibrate_light(light, master_dark=dark)

    # dark current + bias offset should be gone; only star/background signal remains
    assert calibrated.mean() < light.mean()
    assert calibrated.min() >= 0.0


def test_normalize_flat_has_unit_mean():
    rng = _rng()
    flat = rng.normal(30000, 100, (50, 50, 3)).astype(np.float32)
    normalized = calibration.normalize_flat(flat)
    assert np.isclose(normalized.mean(), 1.0, atol=0.05)


def test_normalize_flat_floors_near_zero_corners_relative_to_mean():
    # A flat with a near-black vignette corner (realistic for wide-field optics).
    # An absolute floor like 1e-3 is effectively zero next to a ~30000 mean, which
    # made calibrate_light's later division blow the pixel up by ~1e7x.
    flat = np.full((50, 50, 3), 30000.0, dtype=np.float32)
    flat[0, 0, :] = 0.5  # near-black corner pixel

    normalized = calibration.normalize_flat(flat)

    assert normalized[0, 0, 0] >= 0.05 - 1e-6  # floored at the relative minimum, not ~1.6e-5


def test_normalize_flat_uses_per_channel_mean_not_shared_scalar():
    # Same relative vignetting shape in every channel, but very different absolute
    # brightness per channel (e.g. a saturated/overexposed blue channel next to
    # properly-exposed red/green) -- realistic for real flat frames. A shared
    # global mean across all channels would leave channels inconsistently
    # corrected, which shows up as a spatially-varying color cast on real data.
    yy, xx = np.mgrid[0:40, 0:40].astype(np.float32)
    vignette = 1.0 - 0.5 * (((yy - 20) ** 2 + (xx - 20) ** 2) / (20**2 + 20**2))

    flat = np.stack([vignette * 60000, vignette * 30000, vignette * 45000], axis=-1)  # B, G, R
    normalized = calibration.normalize_flat(flat)

    # every channel should normalize to the same relative pattern despite the very
    # different absolute brightness per channel
    assert np.allclose(normalized[..., 0], normalized[..., 1], atol=1e-3)
    assert np.allclose(normalized[..., 1], normalized[..., 2], atol=1e-3)


def test_clipped_channels_detects_a_saturated_channel():
    # Blue is uniformly at the sensor ceiling (e.g. a flat exposed too long
    # for that channel's gain); green/red aren't.
    frame = np.full((30, 30, 3), 30000.0, dtype=np.float32)
    frame[:, :, 0] = 65535.0

    assert calibration.clipped_channels(frame) == ["B"]


def test_clipped_channels_ignores_a_small_bright_region():
    # A star core saturating a handful of pixels isn't the same problem as a
    # whole channel being blown out -- only a channel clipped over a large
    # fraction of the frame should be flagged.
    frame = np.full((30, 30, 3), 30000.0, dtype=np.float32)
    frame[0:2, 0:2, :] = 65535.0

    assert calibration.clipped_channels(frame) == []


def test_calibrate_light_flat_division_does_not_blow_up_on_vignette_corner():
    flat = np.full((50, 50, 3), 30000.0, dtype=np.float32)
    flat[0, 0, :] = 0.5
    normalized_flat = calibration.normalize_flat(flat)

    light = np.full((50, 50, 3), 5000.0, dtype=np.float32)
    calibrated = calibration.calibrate_light(light, normalized_flat=normalized_flat)

    # Flat-field correction should never turn a legitimate light pixel into
    # something dozens of thousands of times brighter than the rest of the frame --
    # that's what happened when normalized_flat could be ~1e-7 in dark corners.
    assert calibrated[0, 0, 0] < light[0, 0, 0] * 25
    assert calibrated.max() < 1e6


def test_color_calibrate_neutralizes_color_cast_without_zeroing_background():
    rng = _rng()
    light = make_light_frame(rng).astype(np.float32)
    light[:, :, 0] += 50  # inject a blue color cast in the background

    calibrated = color.calibrate(light)

    assert calibrated.shape == light.shape
    mask = color.star_mask(light)
    sky_median = np.median(calibrated[mask == 0.0], axis=0)

    # channels should be neutral (color cast removed) relative to each other...
    assert np.ptp(sky_median) < 5.0
    # ...but the background must NOT be driven down near zero: doing that leaves a
    # subsequent stretch nothing but noise to work with (this was the root cause of
    # a real-world regression -- a clean stacked image turned into a color-speckled
    # gradient purely from this step, even though the math looks like a harmless
    # per-channel constant shift).
    assert sky_median.min() > 1000


def _with_black_border(frame, border):
    """Places a frame inside a larger all-black canvas, returning the padded
    frame plus the boolean coverage mask of the real pixels.

    Padding rather than shifting/warping is deliberate: it reproduces exactly
    the thing being tested (border fill polluting the sky sample) while leaving
    the covered pixels *bit-identical* to the original. A real warp would also
    push stars out of frame and resample the rest, so "the data is unchanged"
    wouldn't hold at synthetic-test frame sizes and the assertions below
    couldn't be tight.
    """
    height, width, channels = frame.shape
    padded = np.zeros((height + 2 * border, width + 2 * border, channels), dtype=frame.dtype)
    padded[border:border + height, border:border + width] = frame
    coverage = np.zeros(padded.shape[:2], dtype=bool)
    coverage[border:border + height, border:border + width] = True
    return padded, coverage


def test_estimate_snr_without_coverage_is_dragged_down_by_alignment_border():
    """Documents *why* coverage is threaded through: the black border fill an
    aligned frame carries lands in the sky sample and inflates its standard
    deviation, so an otherwise-identical frame reads as noticeably noisier.

    Uses a purpose-built frame with a *tight* sky rather than conftest's
    make_light_frame, because the effect depends on the border being a distinct
    second population. make_light_frame carries a strong vignette whose sky
    already spans down toward zero, so exact-zero fill isn't an outlier there
    and the bug doesn't reproduce -- on a real calibrated, gradient-removed
    master (measured: 6.24 dB under-report at 7.5% border) it very much does.
    """
    rng = _rng()
    frame = rng.normal(1500, 40, (200, 260, 3)).clip(0, None).astype(np.float32)
    for row, col in ((40, 60), (120, 180), (160, 90)):
        frame[row - 2:row + 3, col - 2:col + 3] = 30000.0

    baseline = color.estimate_snr(frame)
    padded, _coverage = _with_black_border(frame, 20)
    assert color.estimate_snr(padded) < baseline - 5.0


def test_estimate_snr_with_coverage_ignores_the_alignment_border():
    rng = _rng()
    frame = make_light_frame(rng).astype(np.float32)
    baseline = color.estimate_snr(frame)

    # Growing border, identical covered data -- the measured quality must stay
    # put, otherwise compute_frame_weights under-weights (or outright rejects)
    # frames purely for having needed a larger alignment shift. The covered
    # pixels are bit-identical to the original here, so this is exact.
    for border in (5, 20, 60):
        padded, coverage = _with_black_border(frame, border)
        assert color.estimate_snr(padded, coverage=coverage) == pytest.approx(baseline, abs=1e-6)


def test_star_mask_coverage_excludes_border_from_the_percentile_cutoff():
    rng = _rng()
    frame = make_light_frame(rng).astype(np.float32)
    padded, coverage = _with_black_border(frame, 40)

    # Border zeros sit at the bottom of the distribution, so including them
    # lowers the cutoff and lets ordinary sky qualify as "star".
    assert color.star_mask(padded).sum() > color.star_mask(padded, coverage=coverage).sum()


def test_star_mask_all_covered_matches_no_coverage_argument():
    rng = _rng()
    frame = make_light_frame(rng).astype(np.float32)
    all_covered = np.ones(frame.shape[:2], dtype=bool)
    assert np.array_equal(color.star_mask(frame), color.star_mask(frame, coverage=all_covered))


def test_star_mask_empty_coverage_returns_an_empty_mask():
    rng = _rng()
    frame = make_light_frame(rng).astype(np.float32)
    nothing_covered = np.zeros(frame.shape[:2], dtype=bool)
    assert color.star_mask(frame, coverage=nothing_covered).sum() == 0


def test_estimate_snr_subsample_tracks_the_full_resolution_estimate():
    """Subsampling is only acceptable for per-frame weighting if it preserves
    the value closely enough to rank frames the same way."""
    rng = _rng()
    frame = make_light_frame(rng).astype(np.float32)
    assert abs(color.estimate_snr(frame, subsample=2) - color.estimate_snr(frame)) < 2.0


def test_remove_background_gradient_flattens_a_directional_gradient():
    height, width = 200, 300
    img = np.full((height, width, 3), 700.0, dtype=np.float32)

    # A red-channel-specific left-to-right gradient, like the residual
    # vignette this function targets -- other channels stay flat.
    ramp = np.linspace(0, 400, width, dtype=np.float32)
    img[:, :, 2] += ramp[np.newaxis, :]

    rng = _rng()
    for _ in range(15):
        y, x = rng.integers(10, height - 10), rng.integers(10, width - 10)
        img[y - 2 : y + 2, x - 2 : x + 2] = 30000.0  # small bright "stars"

    corrected = color.remove_background_gradient(img)

    def red_at(col):
        return np.median(corrected[:, col - 5 : col + 5, 2])

    before_spread = ramp[-1] - ramp[0]
    after_spread = abs(red_at(width - 10) - red_at(10))
    assert after_spread < before_spread * 0.15  # gradient largely flattened


def test_remove_background_gradient_preserves_extended_nebula_signal():
    height, width = 200, 300
    img = np.full((height, width, 3), 700.0, dtype=np.float32)

    # A smooth, localized patch well below star_mask's point-source threshold
    # -- extended nebulosity, not a star -- covering a modest corner of the
    # frame, well clear of most of the grid's background cells. A patch broad
    # enough to dominate most of the frame is close to indistinguishable from
    # a real gradient for *any* low-order polynomial method (not just this
    # one) -- this tests the realistic case, a real feature sitting within an
    # otherwise-measurable background, not that worst case.
    yy, xx = np.mgrid[0:height, 0:width]
    nebula = np.exp(-(((yy - 100) ** 2 + (xx - 220) ** 2) / (2 * 20**2))) * 350.0
    for c in range(3):
        img[:, :, c] += nebula

    rng = _rng()
    for _ in range(15):
        y, x = rng.integers(10, height - 10), rng.integers(10, width - 10)
        img[y - 2 : y + 2, x - 2 : x + 2] = 30000.0

    corrected = color.remove_background_gradient(img)

    nebula_level = np.median(corrected[95:105, 215:225, 1])
    plain_background_level = np.median(corrected[:20, :20, 1])
    # the nebula should still read clearly brighter than plain background --
    # not flattened away as if it were part of the gradient.
    assert nebula_level - plain_background_level > 200


def test_remove_background_gradient_leaves_image_untouched_with_no_background_samples():
    img = np.full((50, 50, 3), 700.0, dtype=np.float32)
    all_star_mask = np.ones((50, 50), dtype=np.float32)  # nothing classified as background

    corrected = color.remove_background_gradient(img, mask=all_star_mask)

    assert np.array_equal(corrected, img)


def test_stretch_output_ranges():
    linear = np.array([[[0, 1000, 60000]]], dtype=np.float32)

    u8 = stretch.to_uint8(linear, method="mtf", midtone=0.25)
    assert u8.dtype == np.uint8 and u8.min() >= 0 and u8.max() <= 255

    u16 = stretch.to_uint16(linear, method="asinh", scale=800)
    assert u16.dtype == np.uint16 and u16.min() >= 0 and u16.max() <= 65535


def test_compute_histogram_shape_and_keys():
    rng = _rng()
    img = make_light_frame(rng).astype(np.float32)

    hist = stretch.compute_histogram(img, bins=128)

    assert set(hist.keys()) == {"display_max", "bins", "black_point", "b", "g", "r"}
    assert hist["bins"] == 128
    assert len(hist["b"]) == len(hist["g"]) == len(hist["r"]) == 128
    assert hist["display_max"] > 0
    assert 0.0 <= hist["black_point"] <= hist["display_max"]


def test_compute_histogram_counts_are_log_compressed_and_nonnegative():
    img = np.full((50, 50, 3), 700.0, dtype=np.float32)
    img[10:40, 10:40] = 30000.0  # a big bright block, guaranteed to land in a high bin

    hist = stretch.compute_histogram(img, bins=64)

    assert all(v >= 0 for v in hist["b"])
    # log1p-compressed counts should never exceed log1p(total pixel count)
    assert max(hist["g"]) <= np.log1p(img.shape[0] * img.shape[1]) + 1e-6


def test_compute_histogram_black_point_matches_auto_stretch_shadow_clip():
    rng = _rng()
    img = np.clip(rng.normal(1000, 40, (60, 60, 3)), 0, None).astype(np.float32)
    img[5:10, 5:10] = 30000  # a star, so the background isn't the whole image's max

    hist = stretch.compute_histogram(img, shadow_clip=-2.8)

    # Re-derive the same black point auto_stretch would compute internally,
    # and confirm compute_histogram reports the same value on its own scale.
    normalized = img / np.max(img)
    median = float(np.median(normalized))
    madn = 1.4826 * float(np.median(np.abs(normalized - median)))
    expected_black_point = np.clip(median - 2.8 * madn, 0.0, median) * float(np.max(img))

    assert hist["black_point"] == pytest.approx(expected_black_point, rel=1e-4)


def test_auto_stretch_lifts_dim_linear_background_near_target():
    # A dim linear background relative to a bright star peak -- the scenario that
    # caused the reported "black screen": on genuinely linear data, a fixed
    # midtone (e.g. 0.25) barely lifts the shadows at all.
    rng = _rng()
    img = np.clip(rng.normal(700, 40, (100, 100, 3)), 0, None).astype(np.float32)
    img[10:14, 10:14, :] = 30000  # star

    bg_mask = np.ones((100, 100), dtype=bool)
    bg_mask[5:20, 5:20] = False

    auto = stretch.auto_stretch(img, target_bkg=0.25)
    fixed_mtf = stretch.midtone_transfer_function(img, midtone=0.25)

    assert 0.15 < auto[bg_mask].mean() < 0.35  # lands near the 0.25 target
    assert auto[bg_mask].mean() > fixed_mtf[bg_mask].mean() * 2  # clearly brighter than the old fixed default


def test_auto_stretch_handles_zero_noise_background_without_going_black():
    # Degenerate case: MAD == 0 (no measurable background spread) used to make the
    # computed black point equal the median exactly, clipping the whole background to 0.
    img = np.full((20, 20, 3), 700.0, dtype=np.float32)
    img[0, 0, :] = 30000.0

    auto = stretch.auto_stretch(img, target_bkg=0.25)
    assert auto[10, 10, 0] > 0.15


def test_to_uint8_defaults_to_auto_method():
    rng = _rng()
    img = np.clip(rng.normal(700, 40, (50, 50, 3)), 0, None).astype(np.float32)
    img[5:8, 5:8, :] = 30000

    default_output = stretch.to_uint8(img)
    explicit_auto = stretch.to_uint8(img, method="auto")
    assert np.array_equal(default_output, explicit_auto)


def test_fix_star_halos_preserves_shape_and_dtype():
    rng = _rng()
    img = make_light_frame(rng).astype(np.uint16)
    fixed = halos.fix_star_halos(img)
    assert fixed.shape == img.shape
    assert fixed.dtype == img.dtype


def test_alignment_registers_shifted_frame():
    rng = _rng()
    reference = alignment.ReferenceFrame(make_light_frame(rng).astype(np.float32))
    shifted = make_light_frame(rng, shift_y=5, shift_x=-4).astype(np.float32)

    result = reference.align(shifted)

    assert result is not None
    aligned, valid_mask = result
    assert aligned.shape == reference.bgr.shape
    assert valid_mask.shape == reference.bgr.shape[:2]
    assert valid_mask.dtype == bool


def test_warp_with_coverage_marks_border_fill_as_invalid():
    # A pure translation shifts source content down/right by 10px -- the
    # dst region nothing maps into (top-left 10px strip) should be marked
    # invalid, while a dst region well within the shifted content should be
    # fully valid.
    bgr = np.full((40, 40, 3), 500.0, dtype=np.float32)
    translation = np.array([[1.0, 0.0, 10.0], [0.0, 1.0, 10.0]], dtype=np.float32)

    warped, valid_mask = alignment._warp_with_coverage(bgr, translation, 40, 40)

    assert warped.shape == bgr.shape
    assert valid_mask.shape == (40, 40)
    assert valid_mask.dtype == bool
    assert not valid_mask[:10, :10].any()  # nothing maps into this corner
    assert valid_mask[20:, 20:].all()  # well within the shifted-in content


def _saturation(bgr_pixel):
    b, g, r = bgr_pixel
    peak = max(b, g, r)
    return (peak - min(b, g, r)) / peak if peak > 0 else 0.0


def test_defringe_star_edges_desaturates_purple_ring_without_dimming_it():
    img = np.full((60, 60, 3), 20.0, dtype=np.float32)  # dim sky background
    img[25:35, 25:35] = [255.0, 255.0, 255.0]  # bright white star core
    for row in range(60):
        for col in range(60):
            dist = ((row - 30) ** 2 + (col - 30) ** 2) ** 0.5
            if 5 < dist < 12:
                img[row, col] = [180.0, 40.0, 180.0]  # magenta-ish fringe ring (B, G, R)

    fixed = color.defringe_star_edges(img)

    original = img[30, 38]
    ring_pixel = fixed[30, 38]  # inside the fringe ring, close to the core
    assert _saturation(ring_pixel) < _saturation(original)  # desaturated...
    assert max(ring_pixel) == pytest.approx(max(original), rel=0.05)  # ...without dimming it


def test_defringe_star_edges_leaves_blue_hue_near_a_star_untouched():
    # Real blue reflection-nebula glow can sit right next to a bright star --
    # the hue gate should leave it alone even though it's within the same
    # proximity ring a magenta fringe would be caught in.
    img = np.full((60, 60, 3), 20.0, dtype=np.float32)
    img[25:35, 25:35] = [255.0, 255.0, 255.0]
    for row in range(60):
        for col in range(60):
            dist = ((row - 30) ** 2 + (col - 30) ** 2) ** 0.5
            if 5 < dist < 12:
                img[row, col] = [180.0, 60.0, 40.0]  # blue-ish, not magenta (B, G, R)

    fixed = color.defringe_star_edges(img)

    assert np.allclose(fixed[30, 38], img[30, 38], rtol=0.02)


def test_defringe_star_edges_leaves_distant_purple_color_untouched():
    # A magenta/purple region far from any bright star (e.g. real nebula color)
    # must not get desaturated -- only near-star fringing should be touched.
    # A large canvas keeps the patch well outside the (intentionally wide,
    # feathered) proximity reach around the star. An explicit mask isolates
    # this from star_mask()'s own percentile threshold -- the tiny star core
    # relative to this larger canvas would otherwise pull some of the
    # "distant" patch's pixels into the mask too, since they'd be the
    # second-brightest region in the image.
    img = np.full((150, 150, 3), 20.0, dtype=np.float32)
    img[10:15, 10:15] = [255.0, 255.0, 255.0]  # small bright star, top-left corner
    img[120:135, 120:135] = [150.0, 30.0, 150.0]  # magenta patch, far from the star

    mask = np.zeros((150, 150), dtype=np.float32)
    mask[10:15, 10:15] = 1.0

    fixed = color.defringe_star_edges(img, mask=mask)

    assert np.allclose(fixed[120:135, 120:135], img[120:135, 120:135])


def test_build_calibration_masters_reuses_cache_when_unchanged(synthetic_dataset, tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    call_count = {"n": 0}
    original_build = calibration.build_master_frame

    def counting_build(frame_paths, progress_cb=None):
        call_count["n"] += 1
        return original_build(frame_paths, progress_cb)

    monkeypatch.setattr(calibration, "build_master_frame", counting_build)

    orchestrator.build_calibration_masters(str(synthetic_dataset), output_dir=str(output_dir))
    assert call_count["n"] == 3  # bias, dark, flat all built fresh the first time

    orchestrator.build_calibration_masters(str(synthetic_dataset), output_dir=str(output_dir))
    assert call_count["n"] == 3  # second call reused the cache -- no new builds


def test_build_calibration_masters_rebuilds_when_source_changes(synthetic_dataset, tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    call_count = {"n": 0}
    original_build = calibration.build_master_frame

    def counting_build(frame_paths, progress_cb=None):
        call_count["n"] += 1
        return original_build(frame_paths, progress_cb)

    monkeypatch.setattr(calibration, "build_master_frame", counting_build)

    orchestrator.build_calibration_masters(str(synthetic_dataset), output_dir=str(output_dir))
    assert call_count["n"] == 3

    # Modify just one dark frame's mtime -- only the dark cache should invalidate.
    dark_files = sorted((synthetic_dataset / "darks").glob("*.png"))
    future = time.time() + 10
    os.utime(dark_files[0], (future, future))

    orchestrator.build_calibration_masters(str(synthetic_dataset), output_dir=str(output_dir))
    assert call_count["n"] == 4


def test_build_calibration_masters_without_output_dir_never_caches(synthetic_dataset, monkeypatch):
    call_count = {"n": 0}
    original_build = calibration.build_master_frame

    def counting_build(frame_paths, progress_cb=None):
        call_count["n"] += 1
        return original_build(frame_paths, progress_cb)

    monkeypatch.setattr(calibration, "build_master_frame", counting_build)

    orchestrator.build_calibration_masters(str(synthetic_dataset))
    orchestrator.build_calibration_masters(str(synthetic_dataset))
    assert call_count["n"] == 6  # no output_dir -- nothing to cache into, rebuilds every time


def test_run_pipeline_end_to_end(synthetic_dataset):
    result = orchestrator.run_pipeline(str(synthetic_dataset), sigma=3.0, apply_dark=True, apply_flat=True)

    assert result["stacked_frame_count"] == result["light_frame_count"]
    assert result["applied_dark"] is True
    assert result["applied_flat"] is True
    assert result["rejected_frame_count"] == 0
    assert result["integration_method"] == "sigma_clip"
    assert result["snr_db"] is not None

    master = raw_io.load_linear_master(result["output_path"])
    assert master.shape == (result["height"], result["width"], 3)
    assert master.dtype == np.float32
    assert master.max() > 0
    # The synthetic flat has a near-black vignette corner specifically to catch a
    # regression where flat-field division blew a handful of pixels up to ~1e13-1e14
    # (physically impossible for 16-bit sensor data), which silently wrecked every
    # preview's global-max-based normalization.
    assert master.max() < 1e6
    assert result["calibration_warnings"] == []


def test_run_pipeline_frame_quality_lists_every_light_frame(synthetic_dataset):
    result = orchestrator.run_pipeline(str(synthetic_dataset))

    filenames = {entry["filename"] for entry in result["frame_quality"]}
    assert filenames == {"light_0.png", "light_1.png", "light_2.png", "light_3.png"}
    assert all(entry["status"] == "included" for entry in result["frame_quality"])
    assert all(entry["snr_db"] is not None for entry in result["frame_quality"])


def test_run_pipeline_excluded_frames_are_skipped_and_reported(synthetic_dataset):
    result = orchestrator.run_pipeline(str(synthetic_dataset), excluded_frames=["light_0.png"])

    assert result["light_frame_count"] == 3
    by_filename = {entry["filename"]: entry for entry in result["frame_quality"]}
    assert by_filename["light_0.png"]["status"] == "manually_excluded"
    assert by_filename["light_0.png"]["snr_db"] is None
    assert by_filename["light_1.png"]["status"] == "included"


def test_run_pipeline_reports_a_read_failure_as_error_not_failed_to_align(synthetic_dataset, monkeypatch):
    """A frame that blows up while being read is a different problem from one
    that simply wouldn't register, and the frame-review UI should say so --
    otherwise a corrupt file reads as an alignment problem and sends you
    looking in the wrong place."""
    real_load_frame = raw_io.load_frame

    def exploding_load_frame(path, *args, **kwargs):
        if os.path.basename(path) == "light_3.png":
            raise OSError("simulated unreadable file")
        return real_load_frame(path, *args, **kwargs)

    monkeypatch.setattr(orchestrator.raw_io, "load_frame", exploding_load_frame)
    result = orchestrator.run_pipeline(str(synthetic_dataset))

    entry = {e["filename"]: e for e in result["frame_quality"]}["light_3.png"]
    assert entry["status"] == "error"
    assert "simulated unreadable file" in entry["error"]
    assert entry["snr_db"] is None
    # Frames that succeed carry no error text.
    assert {e["filename"]: e for e in result["frame_quality"]}["light_0.png"]["error"] is None


def test_run_pipeline_reports_a_registration_failure_as_failed_to_align(synthetic_dataset, monkeypatch):
    def never_aligns(self, target_bgr):
        return None

    monkeypatch.setattr(orchestrator.ReferenceFrame, "align", never_aligns)
    with pytest.raises(RuntimeError, match="aligned successfully"):
        orchestrator.run_pipeline(str(synthetic_dataset))


def test_run_pipeline_raises_when_exclusion_leaves_too_few_frames(synthetic_dataset):
    with pytest.raises(ValueError, match="at least 2"):
        orchestrator.run_pipeline(str(synthetic_dataset), excluded_frames=["light_0.png", "light_1.png", "light_2.png"])


def test_run_pipeline_warns_on_a_saturated_flat_channel(tmp_path):
    rng = _rng()
    for sub in ("lights", "darks", "flats", "biases"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)

    for i in range(4):
        cv2.imwrite(str(tmp_path / "biases" / f"bias_{i}.png"), make_bias_frame(rng))
        cv2.imwrite(str(tmp_path / "darks" / f"dark_{i}.png"), make_dark_frame(rng))

        # Same vignette as conftest.make_flat_frame, but blue is pushed to the
        # sensor ceiling everywhere -- the real-world failure mode this is
        # modeling: a channel exposed past clipping carries no vignette shape
        # for calibration to measure.
        yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
        cy, cx = HEIGHT / 2, WIDTH / 2
        vignette = 1.0 - 0.97 * (((yy - cy) ** 2 + (xx - cx) ** 2) / (cx**2 + cy**2))
        flat = (30000 * vignette)[:, :, None] * np.ones(3)
        flat[:, :, 0] = 65535.0
        cv2.imwrite(str(tmp_path / "flats" / f"flat_{i}.png"), flat.clip(0, 65535).astype(np.uint16))

    for i in range(4):
        sy, sx = rng.integers(-6, 6), rng.integers(-6, 6)
        cv2.imwrite(str(tmp_path / "lights" / f"light_{i}.png"), make_light_frame(rng, sy, sx))

    result = orchestrator.run_pipeline(str(tmp_path), apply_dark=True, apply_flat=True)

    assert len(result["calibration_warnings"]) == 1
    assert "flat" in result["calibration_warnings"][0]
    assert "B" in result["calibration_warnings"][0]


def test_clipped_channels_detects_saturation_in_an_8bit_frame():
    """clipped_channels used to hardcode a 16-bit ceiling, so an 8-bit source
    pinned at its own saturation point (255) never registered -- 255 is nowhere
    near 65535, so the check silently always passed."""
    frame = np.full((40, 40, 3), 100.0, dtype=np.float32)
    frame[:, :, 0] = 255.0  # blue pinned at the 8-bit ceiling

    assert calibration.clipped_channels(frame, clip_level=255) == ["B"]
    # The old (default) 16-bit ceiling is what missed it.
    assert calibration.clipped_channels(frame) == []


def test_white_level_for_distinguishes_8bit_and_16bit_images(tmp_path):
    eight = tmp_path / "eight.png"
    sixteen = tmp_path / "sixteen.png"
    cv2.imwrite(str(eight), np.full((8, 8, 3), 200, dtype=np.uint8))
    cv2.imwrite(str(sixteen), np.full((8, 8, 3), 40000, dtype=np.uint16))

    assert raw_io.white_level_for(str(eight)) == 255
    assert raw_io.white_level_for(str(sixteen)) == 65535
    # RAW is decided by extension -- it always decodes at output_bps=16.
    assert raw_io.white_level_for("somewhere/IMG_0001.CR2") == 65535


def test_run_pipeline_warns_on_a_saturated_flat_channel_in_an_8bit_dataset(tmp_path):
    """End-to-end counterpart to the 16-bit warning test above: the same
    saturated-blue flat, written as 8-bit, must still be reported."""
    rng = _rng()
    for sub in ("lights", "darks", "flats", "biases"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)

    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    cy, cx = HEIGHT / 2, WIDTH / 2
    vignette = 1.0 - 0.97 * (((yy - cy) ** 2 + (xx - cx) ** 2) / (cx**2 + cy**2))

    for i in range(4):
        cv2.imwrite(str(tmp_path / "biases" / f"bias_{i}.png"), (make_bias_frame(rng) // 257).astype(np.uint8))
        cv2.imwrite(str(tmp_path / "darks" / f"dark_{i}.png"), (make_dark_frame(rng) // 257).astype(np.uint8))

        flat = (200 * vignette)[:, :, None] * np.ones(3)
        flat[:, :, 0] = 255.0
        cv2.imwrite(str(tmp_path / "flats" / f"flat_{i}.png"), flat.clip(0, 255).astype(np.uint8))

    for i in range(4):
        sy, sx = rng.integers(-6, 6), rng.integers(-6, 6)
        cv2.imwrite(str(tmp_path / "lights" / f"light_{i}.png"), (make_light_frame(rng, sy, sx) // 257).astype(np.uint8))

    result = orchestrator.run_pipeline(str(tmp_path), apply_dark=True, apply_flat=True)

    assert len(result["calibration_warnings"]) == 1
    assert "flat" in result["calibration_warnings"][0]
    assert "B" in result["calibration_warnings"][0]


def test_run_pipeline_without_calibration_still_stacks(synthetic_dataset):
    result = orchestrator.run_pipeline(str(synthetic_dataset), apply_dark=False, apply_flat=False)
    assert result["applied_dark"] is False
    assert result["applied_flat"] is False
    assert result["stacked_frame_count"] >= 2


def test_run_pipeline_median_integration(synthetic_dataset):
    result = orchestrator.run_pipeline(str(synthetic_dataset), integration_method="median")
    assert result["integration_method"] == "median"
    assert result["stacked_frame_count"] >= 2


def test_run_pipeline_winsorized_sigma_clip_integration(synthetic_dataset):
    result = orchestrator.run_pipeline(str(synthetic_dataset), integration_method="winsorized_sigma_clip")
    assert result["integration_method"] == "winsorized_sigma_clip"
    assert result["stacked_frame_count"] >= 2


def test_run_pipeline_reports_quality_rejected_count(synthetic_dataset):
    # The synthetic frames are statistically uniform (same star field/noise
    # model, just shifted) -- none should look like a quality outlier to
    # compute_frame_weights, so this should land at 0 and stacked_frame_count
    # should account for every frame that aligned.
    result = orchestrator.run_pipeline(str(synthetic_dataset))
    assert result["quality_rejected_count"] == 0
    assert result["stacked_frame_count"] == result["light_frame_count"] - result["rejected_frame_count"]


def test_run_pipeline_writes_to_output_dir(synthetic_dataset, tmp_path):
    output_dir = tmp_path / "output"
    result = orchestrator.run_pipeline(str(synthetic_dataset), output_dir=str(output_dir))
    assert result["output_path"] == str(output_dir / orchestrator.LINEAR_MASTER_FILENAME)
    assert output_dir.is_dir()
    # source folder must stay untouched -- workspaces reference frame folders in place
    assert not (synthetic_dataset / orchestrator.LINEAR_MASTER_FILENAME).exists()


def test_normalize_flat_rejects_mismatched_bias_shape_with_clear_error():
    rng = _rng()
    flat = make_flat_frame(rng).astype(np.float32)  # (H, W, 3)
    transposed_bias = make_bias_frame(rng).astype(np.float32).transpose(1, 0, 2)  # (W, H, 3)

    with pytest.raises(ValueError, match="doesn't match"):
        calibration.normalize_flat(flat, master_bias=transposed_bias)


def test_run_pipeline_reports_clear_error_on_orientation_mismatch(synthetic_dataset):
    # Simulate a camera rotated between calibration sessions: bias frames come out
    # transposed relative to the flats/darks/lights. This used to surface as a raw
    # numpy "operands could not be broadcast together" error deep in normalize_flat.
    rng = _rng()
    for path in (synthetic_dataset / "biases").glob("*.png"):
        bias = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        cv2.imwrite(str(path), bias.transpose(1, 0, 2))

    with pytest.raises(ValueError, match="doesn't match"):
        orchestrator.run_pipeline(str(synthetic_dataset))


def test_load_quick_preview_downscales_to_max_dimension(synthetic_dataset):
    light_path = str(sorted((synthetic_dataset / "lights").glob("*.png"))[0])
    full = raw_io.load_frame(light_path)

    preview = raw_io.load_quick_preview(light_path, max_dimension=50)

    assert max(preview.shape[:2]) <= 50
    assert preview.shape[2] == 3
    # aspect ratio preserved
    assert abs((preview.shape[1] / preview.shape[0]) - (full.shape[1] / full.shape[0])) < 0.02


def test_load_quick_preview_leaves_small_images_unscaled(synthetic_dataset):
    light_path = str(sorted((synthetic_dataset / "lights").glob("*.png"))[0])
    full = raw_io.load_frame(light_path)

    preview = raw_io.load_quick_preview(light_path, max_dimension=100000)

    assert preview.shape == full.shape


def test_rotate_zero_degrees_is_a_noop():
    rng = _rng()
    img = make_light_frame(rng).astype(np.float32)
    rotated = transform.rotate(img, 0)
    assert rotated is img  # short-circuited, not just equal


def test_rotate_at_45_degrees_expands_canvas_and_changes_content():
    rng = _rng()
    img = make_light_frame(rng).astype(np.float32)
    rotated = transform.rotate(img, 45)
    # A 45-degree rotation needs a bigger bounding box to avoid losing content
    # off the edges -- the canvas should grow, not stay the original size.
    assert rotated.shape[0] > img.shape[0]
    assert rotated.shape[1] > img.shape[1]
    assert rotated.shape[2] == img.shape[2]


def test_rotate_180_is_a_point_reflection_and_keeps_canvas_size():
    img = np.zeros((40, 60, 3), dtype=np.float32)
    img[5, 5] = [1.0, 1.0, 1.0]  # near top-left corner
    rotated = transform.rotate(img, 180)
    # 180 degrees needs no extra room -- same bounding box as the original.
    assert rotated.shape == img.shape
    # should now land near the bottom-right corner instead
    assert rotated[-6:-4, -6:-4].max() > 0.5
    assert rotated[5, 5].max() < 0.1


def test_rotate_at_90_degrees_swaps_dimensions_without_clipping():
    # The bug this guards against: rotating a wide image by 90 degrees needs
    # a tall canvas -- forcing it back into the original wide canvas (the old
    # behavior) clipped off whatever didn't fit, e.g. content near the top
    # and bottom edges of the now-portrait-oriented result.
    img = np.zeros((40, 100, 3), dtype=np.float32)  # wide: 100 x 40
    img[2:6, 48:52] = 1.0  # a marker near the top edge, mid-width

    rotated = transform.rotate(img, 90)

    assert rotated.shape[0] == img.shape[1]  # height <-> width swap
    assert rotated.shape[1] == img.shape[0]
    assert rotated.max() > 0.5  # the marker survived the rotation, not clipped away


def test_rotated_canvas_size_matches_rotate_output_shape():
    rng = _rng()
    img = make_light_frame(rng).astype(np.float32)
    height, width = img.shape[:2]
    for degrees in (10, 45, 90, 135, 200):
        expected_width, expected_height = transform.rotated_canvas_size(width, height, degrees)
        rotated = transform.rotate(img, degrees)
        assert rotated.shape[:2] == (expected_height, expected_width)


def test_crop_extracts_expected_pixel_region():
    img = np.zeros((100, 200, 3), dtype=np.float32)
    img[25:75, 50:150] = 1.0  # a known bright rectangle

    cropped = transform.crop(img, x=0.25, y=0.25, width=0.5, height=0.5)

    assert cropped.shape == (50, 100, 3)
    assert cropped.min() == 1.0  # the bright rectangle exactly fills the crop


def test_crop_clamps_to_image_bounds():
    img = np.zeros((100, 100, 3), dtype=np.float32)
    cropped = transform.crop(img, x=0.8, y=0.8, width=0.5, height=0.5)  # overshoots past 1.0
    assert cropped.shape == (20, 20, 3)


def test_crop_raises_on_empty_rectangle():
    img = np.zeros((100, 100, 3), dtype=np.float32)
    with pytest.raises(ValueError, match="empty"):
        transform.crop(img, x=1.5, y=0, width=0.1, height=0.1)  # entirely outside bounds


def test_downscale_to_fit_caps_the_longest_edge_and_keeps_aspect():
    img = np.zeros((600, 900, 3), dtype=np.float32)
    out = transform.downscale_to_fit(img, 300)
    assert out.shape == (200, 300, 3)


def test_downscale_to_fit_caps_the_longest_edge_when_portrait():
    img = np.zeros((900, 600, 3), dtype=np.float32)
    assert transform.downscale_to_fit(img, 300).shape == (300, 200, 3)


def test_downscale_to_fit_never_upscales_a_smaller_image():
    img = np.zeros((100, 120, 3), dtype=np.float32)
    assert transform.downscale_to_fit(img, 4000) is img


def test_downscale_to_fit_treats_zero_or_none_as_no_limit():
    img = np.zeros((600, 900, 3), dtype=np.float32)
    assert transform.downscale_to_fit(img, 0) is img
    assert transform.downscale_to_fit(img, None) is img


def test_downscale_to_fit_preserves_dtype_and_overall_level():
    img = np.full((400, 800, 3), 1234.0, dtype=np.float32)
    out = transform.downscale_to_fit(img, 200)
    assert out.dtype == np.float32
    # INTER_AREA averages, so a uniform image must survive unchanged in level.
    assert out.mean() == pytest.approx(1234.0, rel=1e-4)


def test_downscale_to_fit_then_effects_upscale_lands_near_the_budget():
    """api.workspace_preview divides the downscale target by the upscale factor
    so effects' own upscale brings it back to roughly the requested budget --
    otherwise a 3x upscale would encode a preview ~9x larger than asked for."""
    img = np.zeros((2602, 3908, 3), dtype=np.float32)
    budget, upscale = 1600, 3.0

    shrunk = transform.downscale_to_fit(img, round(budget / upscale))
    stretched = stretch.to_uint8(shrunk)
    final = effects.apply(stretched, upscale_factor=upscale)

    assert max(final.shape[:2]) == pytest.approx(budget, abs=upscale)


def test_apply_composes_rotate_then_crop():
    rng = _rng()
    img = make_light_frame(rng).astype(np.float32)

    rotated_only = transform.rotate(img, 10)
    composed = transform.apply(img, rotation_deg=10, crop_rect={"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5})

    expected = transform.crop(rotated_only, x=0.1, y=0.1, width=0.5, height=0.5)
    assert np.array_equal(composed, expected)


def test_apply_with_no_rotation_or_crop_returns_input_unchanged():
    rng = _rng()
    img = make_light_frame(rng).astype(np.float32)
    assert transform.apply(img) is img


def test_adjust_brightness_zero_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.adjust_brightness(img, 0.0) is img


def test_adjust_brightness_shifts_mean_up_and_down():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    brighter = effects.adjust_brightness(img, 0.2)
    darker = effects.adjust_brightness(img, -0.2)
    assert brighter.mean() > img.mean() > darker.mean()
    assert brighter.dtype == img.dtype


def test_adjust_contrast_zero_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.adjust_contrast(img, 0.0) is img


def test_adjust_contrast_increases_spread_around_midpoint():
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    img[:10] = 80
    img[10:] = 175  # values symmetric around the 127.5 midpoint

    contrasted = effects.adjust_contrast(img, 0.5)

    assert contrasted.std() > img.std()


def test_adjust_saturation_one_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.adjust_saturation(img, 1.0) is img


def test_adjust_saturation_zero_desaturates_to_equal_channels():
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    img[:, :, 0] = 40  # B
    img[:, :, 1] = 120  # G
    img[:, :, 2] = 200  # R

    desaturated = effects.adjust_saturation(img, 0.0)

    assert np.ptp(desaturated[0, 0]) < 2  # B/G/R now nearly equal (grayscale)


def test_adjust_vibrance_zero_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.adjust_vibrance(img, 0.0) is img


def test_adjust_vibrance_boosts_moderate_saturation_more_than_already_vivid():
    moderate = np.array([[[150, 120, 180]]], dtype=np.uint8)  # B, G, R -- some saturation
    vivid = np.array([[[255, 0, 100]]], dtype=np.uint8)  # already fully saturated

    def saturation_of(img):
        hsv = cv2.cvtColor(img.astype(np.float32) / 255.0, cv2.COLOR_BGR2HSV)
        return float(hsv[0, 0, 1])

    moderate_gain = saturation_of(effects.adjust_vibrance(moderate, 0.8)) - saturation_of(moderate)
    vivid_gain = saturation_of(effects.adjust_vibrance(vivid, 0.8)) - saturation_of(vivid)
    assert moderate_gain > vivid_gain >= 0


def test_reduce_stars_zero_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    mask = np.zeros((20, 20), dtype=np.float32)
    assert effects.reduce_stars(img, 0.0, star_mask=mask) is img


def test_reduce_stars_dims_the_outer_ring_but_keeps_the_center_bright():
    img = np.full((40, 40, 3), 30, dtype=np.uint8)  # dim background
    img[15:25, 15:25] = 255  # bright star core
    mask = np.zeros((40, 40), dtype=np.float32)
    mask[15:25, 15:25] = 1.0

    reduced = effects.reduce_stars(img, 1.0, star_mask=mask)

    assert reduced[19, 19].mean() > 200  # near-center: still bright
    assert reduced[16, 16].mean() < img[16, 16].mean()  # near the original edge: dimmed toward background


def test_reduce_noise_zero_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.reduce_noise(img, 0.0) is img


def test_reduce_noise_smooths_background_but_protects_masked_stars():
    rng = _rng()
    img = np.clip(100.0 + rng.normal(0, 20, (40, 40, 3)), 0, 255).astype(np.uint8)
    img[15:25, 15:25] = 255  # a bright, noise-free star core
    mask = np.zeros((40, 40), dtype=np.float32)
    mask[15:25, 15:25] = 1.0

    denoised = effects.reduce_noise(img, 1.0, star_mask=mask)

    assert denoised[:10, :10].std() < img[:10, :10].std()  # background noise reduced
    assert abs(int(denoised[19, 19].mean()) - 255) < 10  # star core protected


def test_sharpen_zero_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.sharpen(img, 0.0) is img


def test_sharpen_visibly_changes_a_soft_edge():
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    img[:, 10:] = 200
    sharpened = effects.sharpen(img, 1.0)
    assert not np.array_equal(sharpened, img)
    assert sharpened.shape == img.shape and sharpened.dtype == img.dtype


def test_upscale_factor_one_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.upscale(img, 1.0) is img


def test_upscale_factor_below_one_is_a_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint8)
    assert effects.upscale(img, 0.5) is img


def test_upscale_scales_pixel_dimensions():
    img = np.full((20, 30, 3), 100, dtype=np.uint8)
    result = effects.upscale(img, 2.0)
    assert result.shape == (40, 60, 3)
    assert result.dtype == img.dtype


def test_upscale_rounds_fractional_dimensions():
    img = np.full((21, 33, 3), 100, dtype=np.uint8)
    result = effects.upscale(img, 1.5)
    assert result.shape == (round(21 * 1.5), round(33 * 1.5), 3)


def test_effects_apply_defaults_are_a_full_noop():
    img = np.full((20, 20, 3), 100, dtype=np.uint16)
    assert effects.apply(img) is img


def test_effects_apply_preserves_shape_and_dtype_across_formats():
    rng = _rng()
    img_u8 = stretch.to_uint8(make_light_frame(rng).astype(np.float32))
    result_u8 = effects.apply(img_u8, brightness=0.1, contrast=0.1, saturation=1.3, sharpen_amount=0.5)
    assert result_u8.shape == img_u8.shape and result_u8.dtype == np.uint8

    img_u16 = stretch.to_uint16(make_light_frame(rng).astype(np.float32))
    result_u16 = effects.apply(img_u16, brightness=0.1, contrast=0.1, saturation=1.3, sharpen_amount=0.5)
    assert result_u16.shape == img_u16.shape and result_u16.dtype == np.uint16


def test_effects_apply_with_every_new_param_together():
    rng = _rng()
    img = stretch.to_uint8(make_light_frame(rng).astype(np.float32))
    result = effects.apply(
        img,
        brightness=0.05,
        contrast=0.05,
        saturation=1.1,
        vibrance=0.4,
        star_reduction=0.5,
        noise_reduction=0.5,
        sharpen_amount=0.3,
    )
    assert result.shape == img.shape and result.dtype == img.dtype


def test_effects_apply_upscale_factor_scales_final_output_dimensions():
    rng = _rng()
    img = stretch.to_uint8(make_light_frame(rng).astype(np.float32))
    result = effects.apply(img, upscale_factor=2.0)
    assert result.shape == (img.shape[0] * 2, img.shape[1] * 2, 3)
    assert result.dtype == img.dtype


def test_effects_apply_with_upscale_and_every_other_param_together():
    rng = _rng()
    img = stretch.to_uint8(make_light_frame(rng).astype(np.float32))
    result = effects.apply(
        img,
        brightness=0.05,
        contrast=0.05,
        saturation=1.1,
        vibrance=0.4,
        star_reduction=0.5,
        noise_reduction=0.5,
        upscale_factor=1.5,
        sharpen_amount=0.3,
    )
    assert result.shape == (round(img.shape[0] * 1.5), round(img.shape[1] * 1.5), 3)
    assert result.dtype == img.dtype
