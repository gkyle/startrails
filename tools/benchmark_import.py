"""Compare per-file persistence with one import using temporary real image paths."""
import os
from pathlib import Path
import tempfile
import time


def main():
    with tempfile.TemporaryDirectory(prefix="startrails-import-") as folder:
        os.environ["YOLO_CONFIG_DIR"] = folder
        from PIL import Image
        from startrails.app import App
        from startrails.ui.project import Project

        class ImportApp(App):
            def __init__(self, name):
                self.project = Project(rawInputFiles=[], outputFiles=[], projectFile=str(Path(folder) / name))
                self.stateFile = str(Path(folder) / "app.json")
                self.state = {}
                self.saves = 0

            def saveProject(self):
                self.saves += 1
                super().saveProject()

        paths = []
        for index in range(1000):
            path = Path(folder) / f"image_{index:04}.jpg"
            Image.new("RGB", (8, 8)).save(path)
            paths.append(str(path))
        old = ImportApp("old.project.json")
        start = time.perf_counter()
        for path in paths:
            old.appendInputFile(Path(path).name, path)
        old.sortInputFiles()
        print(f"Per-file persistence: {time.perf_counter() - start:.3f}s, {old.saves} project saves")
        if hasattr(App, "addInputFiles"):
            new = ImportApp("new.project.json")
            start = time.perf_counter()
            new.addInputFiles(paths)
            print(f"Single import: {time.perf_counter() - start:.3f}s, {new.saves} project saves")
            assert [(f.basename, f.path) for f in old.getInputFileList()] == [(f.basename, f.path) for f in new.getInputFileList()]
            new.loadProject(new.project.projectFile)
            assert len(new.getInputFileList()) == 1000
            kept = new.getInputFileList()[0]
            kept.streaksManualMasks = [[[0, 0], [1, 0], [1, 1]]]
            kept.excludeFromStack = True
            new.addInputFiles([paths[-1]])
            assert new.getInputFileList()[0] is kept
            new.loadProject(new.project.projectFile)
            assert new.getInputFileList()[0].streaksManualMasks == kept.streaksManualMasks
            assert new.getInputFileList()[0].excludeFromStack
            new.addInputFiles(paths[:2], clear=True)
            assert len(new.getInputFileList()) == 2
            assert not new.getInputFileList()[0].streaksManualMasks
            print("Append identity, annotation/exclusion round-trip, and replacement checks passed")


if __name__ == "__main__":
    main()
