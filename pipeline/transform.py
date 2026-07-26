"""Non-destructive rotate/crop transforms, applied on demand at preview/export
time -- same philosophy as stretch.py: the saved master (master_linear.npy)
is never mutated, only what's shown/exported reflects the current crop and
rotation.
"""
import math

import cv2


def rotated_canvas_size(width, height, degrees):
    """The bounding-box size that fully contains a width x height image once
    rotated by degrees -- the frontend's imageGeometry.ts mirrors this same
    formula so the live crop-editing preview sizes its canvas identically to
    what rotate() below actually produces.
    """
    rad = math.radians(degrees)
    cos, sin = abs(math.cos(rad)), abs(math.sin(rad))
    return round(width * cos + height * sin), round(width * sin + height * cos)


def rotate(bgr_f32, degrees):
    """Rotates around the image center, expanding the canvas so the entire
    rotated image is preserved (corners introduced by the rotation are filled
    with black) rather than clipping it to the original canvas size -- a
    90-degree rotation of a non-square image, for instance, would otherwise
    lose whatever doesn't fit back inside the original (now wrong-aspect)
    bounding box. The crop box is expected to trim the black corners away
    afterward.
    """
    if not degrees:
        return bgr_f32

    height, width = bgr_f32.shape[:2]
    new_width, new_height = rotated_canvas_size(width, height, degrees)
    center = (width / 2.0, height / 2.0)
    # cv2.getRotationMatrix2D treats a positive angle as counter-clockwise;
    # the frontend's live rotation preview uses CSS's rotate(), where
    # positive is clockwise. Negating here keeps the two in agreement, so the
    # direction shown while editing matches what "Apply Cropping" renders.
    matrix = cv2.getRotationMatrix2D(center, -degrees, 1.0)
    # The matrix above rotates around the original image's own center, but
    # the output canvas is now larger -- shift the translation so the
    # rotated content lands centered in the new, expanded canvas.
    matrix[0, 2] += (new_width - width) / 2.0
    matrix[1, 2] += (new_height - height) / 2.0
    return cv2.warpAffine(
        bgr_f32, matrix, (new_width, new_height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )


def downscale_to_fit(bgr_f32, max_dimension):
    """Shrinks an image so its longest edge is at most max_dimension, preserving
    aspect ratio. Returns the input untouched if it already fits, or if
    max_dimension is falsy/non-positive (the "no limit" case).

    Only ever downscales -- a small image is never blown up to fill the limit.

    INTER_AREA rather than INTER_LINEAR: it averages over the whole source
    footprint of each destination pixel, so it doesn't alias away the
    single-pixel stars that dominate this kind of image. Bilinear samples too
    few source pixels when the scale factor is large and makes faint stars
    flicker in and out depending on where the grid lands.

    Used to render previews at display resolution instead of full sensor
    resolution -- see api.workspace_preview, where the stretch alone cost
    1255 ms on a 10 MP master versus 169 ms at 1600 px.
    """
    if not max_dimension or max_dimension <= 0:
        return bgr_f32

    height, width = bgr_f32.shape[:2]
    longest = max(height, width)
    if longest <= max_dimension:
        return bgr_f32

    scale = max_dimension / longest
    return cv2.resize(
        bgr_f32,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
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
