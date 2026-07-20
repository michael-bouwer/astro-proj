"""Star halo/ring-artifact cleanup, applied to a stretched (display-space) image."""
import cv2
import numpy as np


def fix_star_halos(img_u8_or_u16, bright_threshold=200):
    """Heals the dark ring some optics/sensors leave around bright stars.

    Detects bright star cores, dilates to cover the surrounding ring, and fills
    that ring with a heavily blurred "local background color" estimate, then
    pastes the original (unblurred) star cores back on top.
    """
    gray = cv2.cvtColor(img_u8_or_u16, cv2.COLOR_BGR2GRAY)

    _, binary_bright = cv2.threshold(gray, bright_threshold, np.iinfo(gray.dtype).max, cv2.THRESH_BINARY)
    binary_bright = binary_bright.astype(np.uint8) if binary_bright.dtype != np.uint8 else binary_bright

    kernel = np.ones((5, 5), np.uint8)
    star_plus_ring_mask = cv2.dilate(binary_bright, kernel, iterations=2)

    blurred_bg = cv2.GaussianBlur(img_u8_or_u16, (21, 21), 0)

    fixed = img_u8_or_u16.copy()
    np.copyto(fixed, blurred_bg, where=(star_plus_ring_mask > 0)[:, :, np.newaxis])
    fixed[binary_bright > 0] = img_u8_or_u16[binary_bright > 0]

    return fixed
