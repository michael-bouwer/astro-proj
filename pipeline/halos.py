"""Star halo/ring-artifact cleanup, applied to a stretched (display-space) image."""
import cv2
import numpy as np


def fix_star_halos(img_u8_or_u16, bright_threshold=200):
    """Heals the dark ring some optics/sensors leave around bright stars.

    Detects bright star cores, dilates to cover the surrounding ring, and fills
    that ring with a heavily blurred "local background color" estimate, then
    blends the original (unblurred) star cores back on top. Both mask edges
    are feathered rather than pasted across a hard one-pixel boundary -- a hard
    cutover leaves a visible colored outline around each star, since the
    blurred ring fill and the untouched original rarely share the exact same
    color right at that boundary.
    """
    gray = cv2.cvtColor(img_u8_or_u16, cv2.COLOR_BGR2GRAY)
    max_val = np.iinfo(gray.dtype).max

    _, binary_bright = cv2.threshold(gray, bright_threshold, max_val, cv2.THRESH_BINARY)
    binary_bright = binary_bright.astype(np.uint8) if binary_bright.dtype != np.uint8 else binary_bright

    kernel = np.ones((5, 5), np.uint8)
    star_plus_ring_mask = cv2.dilate(binary_bright, kernel, iterations=2)

    blurred_bg = cv2.GaussianBlur(img_u8_or_u16, (21, 21), 0)

    ring_alpha = cv2.GaussianBlur(star_plus_ring_mask, (9, 9), 0).astype(np.float32) / 255.0
    core_alpha = cv2.GaussianBlur(binary_bright, (9, 9), 0).astype(np.float32) / 255.0

    img_f = img_u8_or_u16.astype(np.float32)
    blurred_f = blurred_bg.astype(np.float32)

    ring_blended = img_f * (1 - ring_alpha[:, :, np.newaxis]) + blurred_f * ring_alpha[:, :, np.newaxis]
    fixed = img_f * core_alpha[:, :, np.newaxis] + ring_blended * (1 - core_alpha[:, :, np.newaxis])

    return np.clip(fixed, 0, max_val).astype(img_u8_or_u16.dtype)
