"""Non-destructive rotate/crop transforms, applied on demand at preview/export
time -- same philosophy as stretch.py: the saved master (master_linear.npy)
is never mutated, only what's shown/exported reflects the current crop and
rotation.
"""
import cv2


def rotate(bgr_f32, degrees):
    """Rotates around the image center, keeping the same canvas size (corners
    introduced by the rotation are filled with black -- the crop box is
    expected to trim those away afterward).
    """
    if not degrees:
        return bgr_f32

    height, width = bgr_f32.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    return cv2.warpAffine(
        bgr_f32, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )


def crop(bgr_f32, x, y, width, height):
    """x, y, width, height are normalized [0, 1] fractions of the image, so the
    same rect applies whether it was picked on a small preview JPEG or applied
    to the full-resolution master. Clamped to the image bounds.
    """
    img_height, img_width = bgr_f32.shape[:2]

    x0 = max(0, min(img_width, round(x * img_width)))
    y0 = max(0, min(img_height, round(y * img_height)))
    x1 = max(0, min(img_width, round((x + width) * img_width)))
    y1 = max(0, min(img_height, round((y + height) * img_height)))

    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"Crop rectangle is empty after clamping to image bounds: ({x}, {y}, {width}, {height})")

    return bgr_f32[y0:y1, x0:x1]


def apply(bgr_f32, rotation_deg=0.0, crop_rect=None):
    """Rotates first, then crops the rotated result -- crop_rect is defined in
    the rotated image's coordinate space, matching how the crop overlay is
    shown on top of an already-rotated preview.
    """
    result = rotate(bgr_f32, rotation_deg)
    if crop_rect is not None:
        result = crop(result, **crop_rect)
    return result
