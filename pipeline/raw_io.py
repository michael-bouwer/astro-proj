"""Frame loading and master-image persistence.

Everything in this module deals in linear, unstretched float32 BGR data.
Any nonlinear stretch belongs in stretch.py, applied only at preview/export time.
"""
import os

import cv2
import numpy as np
import rawpy

RAW_EXTS = (".cr2", ".cr3", ".nef", ".arw", ".dng")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tiff", ".tif")
VALID_EXTS = RAW_EXTS + IMAGE_EXTS


def list_frames(directory):
    """Sorted list of calibration/light frame paths in a directory. Empty list if missing."""
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(VALID_EXTS)
    )


def load_frame(file_path, half_size=False):
    """Loads a single frame (raw or image) as linear float32 BGR, camera white balance applied.

    half_size decodes raw files at half resolution -- much faster, only intended
    for quick UI feedback (e.g. load_quick_preview below), never for the actual
    calibration/stacking pipeline which needs full resolution.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in RAW_EXTS:
        with rawpy.imread(file_path) as raw:
            # no_auto_bright preserves linearity: rawpy won't rescale exposure per-frame,
            # which would break calibration-frame subtraction and stack normalization.
            # user_flip=0 forces sensor-native orientation instead of each frame's own
            # embedded EXIF rotation -- otherwise a light/dark/flat/bias set shot with the
            # camera rotated between sessions decodes to inconsistent (transposed) array
            # shapes and calibration/stacking arithmetic fails with a broadcast error.
            rgb = raw.postprocess(
                half_size=half_size,
                use_camera_wb=True,
                no_auto_bright=True,
                gamma=(1, 1),
                output_bps=16,
                user_flip=0,
            )
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        bgr = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
        if bgr is None:
            raise ValueError(f"Could not read frame: {file_path}")
        if bgr.ndim == 2:
            bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    return bgr.astype(np.float32)


def load_quick_preview(file_path, max_dimension=900):
    """Fast, low-res decode for UI feedback (e.g. a blurred loading placeholder) --
    not used for the actual stacking pipeline, which needs full resolution.
    """
    frame = load_frame(file_path, half_size=True)
    height, width = frame.shape[:2]
    scale = min(1.0, max_dimension / max(height, width))
    if scale < 1.0:
        frame = cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    return frame


def to_gray_u8(bgr_f32):
    """Normalized 8-bit grayscale, used for feature detection / alignment only."""
    gray = cv2.cvtColor(bgr_f32, cv2.COLOR_BGR2GRAY)
    return cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def save_linear_master(path, array_f32):
    """Persists the linear (unstretched) calibrated/stacked master for later preview/export."""
    np.save(path, array_f32.astype(np.float32))


def load_linear_master(path):
    return np.load(path).astype(np.float32)


def save_tiff16(path, array_u16):
    cv2.imwrite(path, array_u16)


def encode_jpeg(array_u8, quality=92):
    ok, encoded = cv2.imencode(".jpg", array_u8, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return encoded.tobytes()
