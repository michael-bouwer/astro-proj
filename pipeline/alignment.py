"""Frame registration (alignment to a reference frame).

Primary method is astroalign: it matches asterisms (triangles of stars) rather
than local feature descriptors, which is the current standard for astronomical
registration -- it's robust to the sparse, near-featureless-except-for-points
star fields where descriptor matchers like ORB (the original approach here)
tend to produce noisy or too-few matches. ORB+RANSAC is kept as a fallback for
frames astroalign can't solve (e.g. too few detected stars).
"""
import astroalign
import cv2
import numpy as np

_orb = cv2.ORB_create(nfeatures=3000)
_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def _align_orb(ref_gray, ref_kp, ref_des, target_gray, target_bgr, height, width):
    kp_tgt, des_tgt = _orb.detectAndCompute(target_gray, None)
    if des_tgt is None:
        return None

    matches = _matcher.match(ref_des, des_tgt)
    matches = sorted(matches, key=lambda m: m.distance)[: int(len(matches) * 0.15)]
    if len(matches) < 4:
        return None

    src_pts = np.float32([ref_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_tgt[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    matrix, _ = cv2.estimateAffinePartial2D(dst_pts, src_pts, method=cv2.RANSAC, ransacReprojThreshold=5.0)
    if matrix is None:
        return None

    return cv2.warpAffine(target_bgr, matrix, (width, height))


class ReferenceFrame:
    """Precomputes what's needed to align other frames to a chosen reference."""

    def __init__(self, ref_bgr):
        self.bgr = ref_bgr
        self.height, self.width, _ = ref_bgr.shape
        self.gray = cv2.normalize(
            cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2GRAY), None, 0, 255, cv2.NORM_MINMAX
        ).astype(np.uint8)
        self._orb_kp, self._orb_des = _orb.detectAndCompute(self.gray, None)

    def align(self, target_bgr):
        """Returns the target frame warped into this reference's coordinate frame, or None."""
        target_gray = cv2.normalize(
            cv2.cvtColor(target_bgr, cv2.COLOR_BGR2GRAY), None, 0, 255, cv2.NORM_MINMAX
        ).astype(np.uint8)

        try:
            transform, _matched = astroalign.find_transform(target_gray, self.gray)
            matrix = transform.params[:2]
            return cv2.warpAffine(target_bgr, matrix, (self.width, self.height))
        except (astroalign.MaxIterError, ValueError):
            return _align_orb(
                self.gray, self._orb_kp, self._orb_des, target_gray, target_bgr, self.height, self.width
            )
