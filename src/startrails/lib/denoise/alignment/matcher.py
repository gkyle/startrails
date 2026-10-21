"""Star matching using asterism/triangle invariants and descriptor matching with RANSAC."""

from __future__ import annotations
from typing import List, Optional, Tuple
import cv2
import numpy as np
from scipy.spatial import KDTree

from startrails.lib.denoise.alignment.detector import Star


class StarMatcher:
    """Finds star correspondences between two frames using triangle asterism invariants."""

    @classmethod
    def match_stars(
        cls,
        ref_stars: List[Star],
        target_stars: List[Star],
        max_stars: int = 500,
        tolerance: float = 0.015,
        ransac_thresh: float = 3.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Find matching star coordinates (N, 2) between reference and target frames."""
        if len(ref_stars) < 3 or len(target_stars) < 3:
            return np.empty((0, 2), dtype=np.float32), np.empty((0, 2), dtype=np.float32)

        r_stars = ref_stars[:max_stars]
        t_stars = target_stars[:max_stars]

        r_pts = np.array([[s.x, s.y] for s in r_stars], dtype=np.float32)
        t_pts = np.array([[s.x, s.y] for s in t_stars], dtype=np.float32)

        r_triangles, r_indices = cls._build_triangle_features(r_pts)
        t_triangles, t_indices = cls._build_triangle_features(t_pts)

        if len(r_triangles) == 0 or len(t_triangles) == 0:
            return np.empty((0, 2), dtype=np.float32), np.empty((0, 2), dtype=np.float32)

        tree = KDTree(r_triangles)
        dists, match_idx = tree.query(t_triangles, distance_upper_bound=tolerance)

        votes: dict[Tuple[int, int], int] = {}
        for t_tri_i, (dist, r_tri_i) in enumerate(zip(dists, match_idx)):
            if r_tri_i < len(r_triangles):
                r_tri = r_indices[r_tri_i]
                t_tri = t_indices[t_tri_i]
                for r_star_i, t_star_i in zip(r_tri, t_tri):
                    pair = (r_star_i, t_star_i)
                    votes[pair] = votes.get(pair, 0) + 1

        if len(votes) < 3:
            return np.empty((0, 2), dtype=np.float32), np.empty((0, 2), dtype=np.float32)

        matched_pairs = [(r_idx, t_idx) for (r_idx, t_idx), count in votes.items() if count >= 2]
        if len(matched_pairs) < 3:
            matched_pairs = sorted(votes.keys(), key=lambda k: votes[k], reverse=True)[:max(6, len(votes))]

        pts_ref = np.array([r_pts[r_idx] for r_idx, _ in matched_pairs], dtype=np.float32)
        pts_target = np.array([t_pts[t_idx] for _, t_idx in matched_pairs], dtype=np.float32)

        unique_t, u_idx = np.unique(pts_target, axis=0, return_index=True)
        pts_ref = pts_ref[u_idx]
        pts_target = unique_t

        if len(pts_ref) >= 4:
            _, inliers = cv2.findHomography(pts_target, pts_ref, cv2.RANSAC, ransacReprojThreshold=ransac_thresh)
            if inliers is not None:
                mask = inliers.ravel() == 1
                if np.sum(mask) >= 4:
                    return pts_ref[mask], pts_target[mask]

        if len(pts_ref) >= 3:
            _, inliers = cv2.estimateAffinePartial2D(pts_target, pts_ref, ransacReprojThreshold=ransac_thresh)
            if inliers is not None:
                mask = inliers.ravel() == 1
                if np.sum(mask) >= 3:
                    pts_ref = pts_ref[mask]
                    pts_target = pts_target[mask]

        return pts_ref, pts_target

    @staticmethod
    def _build_triangle_features(
        pts: np.ndarray,
        k_neighbors: int = 7,
    ) -> Tuple[np.ndarray, List[Tuple[int, int, int]]]:
        """Generate scale- and rotation-invariant triangle side length ratio features."""
        n = len(pts)
        if n < 3:
            return np.empty((0, 2), dtype=np.float32), []

        features = []
        indices = []

        tree = KDTree(pts)
        k = min(k_neighbors, n)
        _, neighbors = tree.query(pts, k=k)

        for i in range(n):
            nbrs = [nb for nb in neighbors[i] if nb > i]
            for j_idx in range(len(nbrs)):
                j = nbrs[j_idx]
                for k_idx in range(j_idx + 1, len(nbrs)):
                    k_star = nbrs[k_idx]
                    p1, p2, p3 = pts[i], pts[j], pts[k_star]

                    d12 = float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))
                    d23 = float(np.hypot(p2[0] - p3[0], p2[1] - p3[1]))
                    d31 = float(np.hypot(p3[0] - p1[0], p3[1] - p1[1]))

                    sides = [(d12, (i, j, k_star)), (d23, (j, k_star, i)), (d31, (k_star, i, j))]
                    sides.sort(key=lambda s: s[0])

                    s_min, s_mid, s_max = sides[0][0], sides[1][0], sides[2][0]
                    if s_max > 5.0:
                        r1 = s_min / s_max
                        r2 = s_mid / s_max
                        features.append([r1, r2])
                        # The opposite vertex is stable when detections reorder a triangle.
                        indices.append((sides[0][1][2], sides[1][1][2], sides[2][1][2]))

        return np.array(features, dtype=np.float32), indices
