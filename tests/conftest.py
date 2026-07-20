"""Synthetic frame/dataset generation for tests.

Real CR2 light/dark/flat/bias frames are large and not checked into the repo,
so tests exercise the pipeline against synthetic 16-bit frames with known star
positions, injected hot pixels, and a vignette instead.
"""
import cv2
import numpy as np
import pytest

HEIGHT, WIDTH = 200, 260
BIAS_LEVEL = 500
DARK_LEVEL = 200

# A real star field has many stars at varying brightness; too few (or too
# uniform) and triangle-matching alignment algorithms run out of distinct
# invariants to match between frames. 25 stars with varied intensity mimics
# a real field closely enough for astroalign to register reliably.
_star_rng = np.random.default_rng(99)
STAR_POSITIONS = list(
    zip(
        _star_rng.integers(15, HEIGHT - 15, 25).tolist(),
        _star_rng.integers(15, WIDTH - 15, 25).tolist(),
    )
)
STAR_BRIGHTNESS = _star_rng.uniform(8000, 30000, 25)


def _rng():
    return np.random.default_rng(1234)


def make_bias_frame(rng):
    return rng.normal(BIAS_LEVEL, 15, (HEIGHT, WIDTH, 3)).clip(0, 65535).astype(np.uint16)


def make_dark_frame(rng):
    img = rng.normal(BIAS_LEVEL + DARK_LEVEL, 20, (HEIGHT, WIDTH, 3))
    img[5, 5] = 60000  # hot pixel
    img[HEIGHT - 5, WIDTH - 5] = 60000
    return img.clip(0, 65535).astype(np.uint16)


def make_flat_frame(rng):
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    cy, cx = HEIGHT / 2, WIDTH / 2
    # Vignette drops to near-zero at the extreme corners (severe but realistic for
    # wide-field optics) so tests actually exercise the near-zero-flat divide-by-zero
    # guard in calibration.normalize_flat, instead of staying safely above it.
    vignette = 1.0 - 0.97 * (((yy - cy) ** 2 + (xx - cx) ** 2) / (cx**2 + cy**2))
    flat = (30000 * vignette)[:, :, None] * np.ones(3)
    flat += rng.normal(0, 50, (HEIGHT, WIDTH, 3))
    return flat.clip(0, 65535).astype(np.uint16)


def make_light_frame(rng, shift_y=0, shift_x=0):
    img = rng.normal(BIAS_LEVEL + DARK_LEVEL + 800, 40, (HEIGHT, WIDTH, 3))
    for (sy, sx), brightness in zip(STAR_POSITIONS, STAR_BRIGHTNESS):
        y, x = sy + shift_y, sx + shift_x
        if 3 <= y < HEIGHT - 3 and 3 <= x < WIDTH - 3:
            color = (brightness * 0.9, brightness, brightness * 0.95)
            cv2.circle(img, (x, y), 3, color, -1)
    return img.clip(0, 65535).astype(np.uint16)


def write_dataset(output_dir, num_lights=4, num_calibration=4):
    """Builds a lights/darks/flats/biases dataset of synthetic frames under output_dir."""
    rng = _rng()
    for sub in ("lights", "darks", "flats", "biases"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    for i in range(num_calibration):
        cv2.imwrite(str(output_dir / "biases" / f"bias_{i}.png"), make_bias_frame(rng))
    for i in range(num_calibration):
        cv2.imwrite(str(output_dir / "darks" / f"dark_{i}.png"), make_dark_frame(rng))
    for i in range(num_calibration):
        cv2.imwrite(str(output_dir / "flats" / f"flat_{i}.png"), make_flat_frame(rng))
    for i in range(num_lights):
        sy, sx = rng.integers(-6, 6), rng.integers(-6, 6)
        cv2.imwrite(str(output_dir / "lights" / f"light_{i}.png"), make_light_frame(rng, sy, sx))

    return output_dir


@pytest.fixture
def synthetic_dataset(tmp_path):
    """Builds a small synthetic dataset under a temp directory."""
    return write_dataset(tmp_path)
