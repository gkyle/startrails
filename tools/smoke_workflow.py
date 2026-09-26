"""Run the actual UI queue and operations in a disposable project.

Run from the repository root. --ml also exercises the local detection/fill models.
No model downloads or writes to the user's project are needed.
"""
import argparse
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ml", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="startrails-workflow-") as directory:
        folder = Path(directory)
        os.environ["YOLO_CONFIG_DIR"] = directory
        import cv2
        import numpy as np
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from startrails.app import App
        from startrails.ui.project import Project
        from startrails.ui.ui_wrap import MainWindow

        class TempApp(App):
            def __init__(self):
                self.project = Project(rawInputFiles=[], outputFiles=[], projectFile=str(folder / "smoke.project.json"))
                self.stateFile = str(folder / "app.json")
                self.state = {}
                self.activeOperation = None
                self.gpuInfo = SimpleNamespace(getGpuPresent=lambda: False)
                self.saveProject()

        qt = QApplication.instance() or QApplication([])
        qt.setStyle("Fusion")
        app = TempApp()
        images = []
        paths = []
        for index in range(2):
            pixels = np.zeros((512, 512, 3), dtype=np.uint8)
            pixels[100 + index * 20:104 + index * 20, 80:400] = (60, 120, 200)
            path = folder / f"input-{index}.tif"
            assert cv2.imwrite(str(path), pixels)
            images.append(pixels)
            paths.append(str(path))
        app.addInputFiles(paths)
        window = MainWindow(app)
        ui = window.ui
        qt.processEvents()

        def run(button, label):
            assert button.isEnabled(), f"{label} unexpectedly disabled"
            start = time.perf_counter()
            button.click()
            while not ui.op_queue.waitForDone(10):
                qt.processEvents()
                if time.perf_counter() - start > 180:
                    raise TimeoutError(label)
            qt.processEvents()
            print(f"{label}: {time.perf_counter() - start:.3f}s", flush=True)

        try:
            ui.sidebar.stack.ui.fade.setCurrentIndex(0)
            ui.sidebar.stack.ui.useGPU.setChecked(False)
            ui.sidebar.stack.ui.batchSize.setValue(1)
            run(ui.pushButton_stackImages, "Stack without detection")
            stacked = app.getOutputFileList()[-1]
            assert Path(stacked.path).is_file()
            np.testing.assert_array_equal(cv2.imread(stacked.path), np.maximum(*images))
            assert ui.outputFiles.current_file() is stacked
            assert ui.pushButton_fillGaps.isEnabled()

            if args.ml:
                # Sentinel list identity proves inference replaced masks even if
                # the synthetic image legitimately contains zero detections.
                sentinels = [file.streaksMasks for file in app.getInputFileList()]
                ui.sidebar.detect.ui.useGPU.setChecked(False)
                run(ui.pushButton_removeStreaks, "Detect Streaks (local CPU model)")
                assert all(file.streaksMasks is not sentinel for file, sentinel in zip(app.getInputFileList(), sentinels))
                ui.showFile(stacked)
                run(ui.pushButton_fillGaps, "Fill Gaps (local model)")
                assert {file.operation for file in app.getOutputFileList()} >= {"Stacked", "FillGaps", "FillGapsMask"}
                assert all(Path(file.path).is_file() for file in app.getOutputFileList())

            first = app.getInputFileList()[0]
            first.streaksManualMasks = [np.array([[80, 100], [400, 100], [400, 104], [80, 104]], dtype=np.int64)]
            first.streaksManualDeletedMasks = [np.array([[80, 120], [400, 120], [400, 124], [80, 124]], dtype=np.int64)]
            ui.slotUpdateFile(first)
            mask_dir, training_dir = folder / "masks", folder / "training"
            mask_dir.mkdir()
            training_dir.mkdir()
            with patch.object(QFileDialog, "getExistingDirectory", return_value=str(mask_dir)):
                run(ui.pushButton_exportMasks, "Export Masks")
            assert len(list(mask_dir.glob("*.tif"))) == 2
            assert cv2.imread(str(mask_dir / "masked_input-0.tif"))[101, 100].max() == 0
            with patch.object(QFileDialog, "getExistingDirectory", return_value=str(training_dir)), \
                 patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                run(ui.pushButton_exportTraining, "Export Training")
            assert list(training_dir.rglob("*.txt")), "No training labels exported"

            ui.slotExcludeFile(first)
            app.loadProject(app.project.projectFile)
            ui.resetProjectView()
            restored = app.getInputFileList()[0]
            assert restored.excludeFromStack
            np.testing.assert_array_equal(restored.streaksManualMasks[0], first.streaksManualMasks[0])
            assert ui.inputFiles.model.rowCount() == 2
            print("Output pixels, optional exports, and project persistence verified", flush=True)
        finally:
            window.close()
            ui.op_queue.waitForDone()


if __name__ == "__main__":
    main()
