"""Analytical blend results, sparse preview reconstruction, and cache isolation."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np

from support import IsolatedTestCase
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor


class HorizonCompositorTests(IsolatedTestCase):
    def test_disabled_and_weighted_blends_match_analytical_rgb_and_grayscale(self):
        for rgb in (False, True):
            with self.subTest(rgb=rgb):
                shape = (40, 60, 3) if rgb else (40, 60)
                sky = np.full(shape, 0.8, np.float32)
                ground = np.full(shape, 0.2, np.float32)
                mask = np.zeros(shape[:2], np.float32)
                mask[:25] = 1
                gradient = np.zeros_like(mask)
                gradient[0:4, 0:5] = 0.5
                gradient[18:28, 45:] = 1
                compositor = HorizonCompositor(sky, ground, gradient, mask, feather_radius=0)
                alpha = mask[..., None] if rgb else mask
                base = alpha * sky + (1 - alpha) * ground
                np.testing.assert_allclose(compositor.composite(enable_corrections=False), base, atol=1e-7, rtol=0)
                # At g=.5 smoothstep=.5; at g=1 it is 1, and ground is excluded by the sky mask.
                weight = gradient.copy()
                weight *= mask
                weight = weight[..., None] if rgb else weight
                for blend in (0, 100, 30):
                    result = compositor.composite(
                        horizon_blend_percent=blend, denoise_enabled=False, horizon_blur_radius=0
                    )
                    expected = (
                        alpha * (sky * (1 - weight * blend / 100) + ground * weight * blend / 100)
                        + (1 - alpha) * ground
                    )
                    np.testing.assert_allclose(result, expected, atol=1e-7, rtol=0)
                    preview = base.copy()
                    patches = compositor.composite_patches(
                        horizon_blend_percent=blend,
                        denoise_enabled=False,
                        horizon_blur_radius=0,
                        horizon_denoise_strength=0,
                        enable_corrections=True,
                        horizon_color_denoise_strength=0,
                        horizon_value_denoise_strength=0,
                    )
                    for pixels, (x, y, width, height) in patches:
                        preview[y : y + height, x : x + width] = pixels
                    np.testing.assert_allclose(preview, expected, atol=1e-7, rtol=0)

    def test_concurrent_settings_and_cancellation_do_not_contaminate_cached_output(self):
        sky = np.full((32, 40, 3), 0.8, np.float32)
        ground = np.full_like(sky, 0.2)
        mask = np.ones(sky.shape[:2], np.float32)
        compositor = HorizonCompositor(sky, ground, mask, mask, feather_radius=0)

        def evaluate(blend):
            return compositor.composite(horizon_blend_percent=blend, denoise_enabled=False, horizon_blur_radius=0)

        blends = (0, 100, 50, 0)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(evaluate, blends))
        for blend, result in zip(blends, results):
            np.testing.assert_allclose(result, 0.8 - 0.6 * blend / 100, atol=1e-7, rtol=0)
        self.assertIsNone(compositor.composite(cancel_check=lambda: True))
        np.testing.assert_allclose(evaluate(0), sky, atol=1e-7, rtol=0)
