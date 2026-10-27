"""Sky inference sizing with the bundled processor configuration."""

from contextlib import chdir
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import numpy as np
import torch
from transformers import AutoImageProcessor

from startrails.lib.denoise.sky_detector import AutoSkyDetector


class SkyDetectorTests(TestCase):
    def test_inference_respects_input_limit_and_preserves_aspect_ratio(self):
        work_dir = self.enterContext(TemporaryDirectory(prefix="startrails_sky_"))
        self.enterContext(chdir(work_dir))
        model_path = AutoSkyDetector.DEFAULT_NIGHT_MODEL
        processor = AutoImageProcessor.from_pretrained(model_path, local_files_only=True)
        image = np.zeros((600, 1200, 3), np.uint8)
        for input_size, expected_shape in ((256, (128, 256)), (1024, (512, 1024)), (2048, (600, 1200))):
            with self.subTest(input_size=input_size):
                model = Mock(return_value=SimpleNamespace(logits=torch.zeros((1, 3, 2, 2))))
                with patch.object(AutoSkyDetector, "_get_segformer_model", return_value=(processor, model, "cpu", 2)):
                    mask = AutoSkyDetector.detect(image, device="cpu", input_size=input_size)
                pixel_values = model.call_args.kwargs["pixel_values"]
                self.assertEqual(tuple(pixel_values.shape), (1, 3, *expected_shape))
                self.assertEqual(mask.shape, image.shape[:2])
                self.assertEqual(mask.dtype, np.float32)
                self.assertTrue(np.isfinite(mask).all())
                self.assertTrue(((mask >= 0) & (mask <= 1)).all())
