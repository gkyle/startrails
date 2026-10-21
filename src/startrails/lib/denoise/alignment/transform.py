"""Transformation estimation: Euclidean, Affine, and Homography."""

from __future__ import annotations
from typing import Optional
import cv2
import numpy as np


class TransformModel:
    """Estimates geometric transformation mapping target frame to reference frame."""

    @classmethod
    def estimate(
        cls,
        pts_target: np.ndarray,
        pts_ref: np.ndarray,
        ransac_thresh: float = 2.5,
        **kwargs,
    ) -> Optional[np.ndarray]:
        """Estimate transformation matrix mapping target frame to reference frame.

        For astrophotography star fields, celestial sphere rotation under planar
        perspective projection is fundamentally projective (3x3 homography).

        Returns:
            - 3x3 matrix if homography
            - 2x3 matrix if affine fallback
            - None if estimation failed
        """
        if len(pts_target) < 3 or len(pts_ref) < 3:
            return None

        # Projective homography for celestial sphere rotation
        if len(pts_target) >= 4:
            H, mask = cv2.findHomography(
                pts_target, pts_ref, cv2.RANSAC, ransacReprojThreshold=ransac_thresh
            )
            if H is not None:
                det = float(np.linalg.det(H))
                if abs(det) > 1e-6 and np.all(np.isfinite(H)):
                    return H

        # Rigid partial affine fallback (rotation + translation + uniform scale)
        matrix, _ = cv2.estimateAffinePartial2D(
            pts_target, pts_ref, method=cv2.RANSAC, ransacReprojThreshold=ransac_thresh
        )
        if matrix is not None:
            return matrix

        # Fallback to simple affine if partial failed
        matrix, _ = cv2.estimateAffine2D(pts_target, pts_ref)
        return matrix
