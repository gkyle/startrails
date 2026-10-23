"""Inference adapter contracts, without model weights or accelerator hardware."""

from concurrent.futures import CancelledError
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import cv2
import torch

from support import IsolatedTestCase
from startrails.op.detectStreaks import DetectStreaks, StreaksPredictor
from startrails.lib.file import InputFile


class PredictionBatchTests(IsolatedTestCase):
    def make_detector(self):
        with patch("startrails.op.detectStreaks.YOLO"):
            return DetectStreaks(useGPU=False)

    def test_empty_tiles_do_not_invoke_model(self):
        detector = self.make_detector()
        self.assertEqual(detector.predict([], conf=0.25, batchSize=16, imgsz=512), [])
        detector.model.assert_not_called()

    def test_inference_failure_is_reported_instead_of_completing_frame(self):
        detector = self.make_detector()
        path = self.root / "input.png"
        self.assertTrue(cv2.imwrite(str(path), np.zeros((32, 32, 3), np.uint8)))
        frame = InputFile(path.name, str(path))
        with patch.object(detector, "predict", side_effect=RuntimeError("Inference failed")):
            with self.assertLogs("startrails.op.detectStreaks", level="ERROR") as records:
                with self.assertRaisesRegex(RuntimeError, "Inference failed"):
                    detector.detectStreaks([frame], 0.3, "NMS", 0.2)
        self.assertIn(str(path), "\n".join(records.output))
        self.assertEqual(detector.job.count, 0)

    def test_interrupt_stops_before_next_batch(self):
        detector = self.make_detector()
        detector.startJob(1)

        def predict(inputs, **kwargs):
            detector.requestInterrupt()
            return [Mock()]

        detector.model.side_effect = predict
        with self.assertRaises(CancelledError):
            detector.predict([object(), object()], conf=0.25, batchSize=1, imgsz=512)
        self.assertEqual(detector.model.call_count, 1)

    def test_slow_nms_does_not_drop_later_tiles(self):
        predictor = object.__new__(StreaksPredictor)
        predictor.args = SimpleNamespace(conf=0.25, iou=0.7, classes=None, agnostic_nms=False, max_det=300)
        predictor.model = SimpleNamespace(names={0: "streak"}, end2end=False)
        predictor.construct_results = lambda predictions, img, originals: predictions
        # Two unambiguous rotated boxes per image. Simulate a long first NMS
        # pass; the default deadline would return empty detections for tile 2.
        raw = torch.tensor([[[20.0, 100.0], [20.0, 100.0], [10.0, 10.0], [5.0, 5.0], [0.9, 0.8], [0.1, 0.1]]] * 2)
        with patch("ultralytics.utils.nms.time.time", side_effect=[0.0, 100.0, 200.0]):
            results = predictor.postprocess(raw, None, [np.zeros((1, 1, 3))] * 2)
        self.assertEqual([len(result) for result in results], [2, 2])

    def test_numpy_tiles_are_batched_without_losing_or_reordering_results(self):
        detector = self.make_detector()
        images = [np.full((2, 2, 3), i, np.uint8) for i in range(5)]
        batches = []

        def infer(inputs, **kwargs):
            ids = [int(image[0, 0, 0]) for image in inputs]
            batches.append(ids)
            return [SimpleNamespace(cpu=lambda i=i: i) for i in ids]

        detector.model.side_effect = infer
        self.assertEqual(detector.predict(images, conf=0.25, batchSize=2, imgsz=512), list(range(5)))
        self.assertEqual(batches, [[0, 1], [2, 3], [4]])
