"""Unit tests for Finish project persistence, source I/O, export policy, and mode routing."""

from pathlib import Path
import os
import shutil
import cv2
import jsonpickle
import numpy as np
from PySide6.QtCore import QObject

from support import QtTestCase
from startrails.lib.finish.defaults import (
    BLEND_SCREEN,
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
)
from startrails.lib.image_io import imwrite
from startrails.lib.project import Project
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.project_finish import FinishProject, probe_source_image
from startrails.lib.project_type import (
    FINISH_EXT as PT_FINISH_EXT,
    TYPE_DENOISE,
    TYPE_FINISH,
    TYPE_STARTRAILS,
    UnsupportedProjectError,
    detect_project_type,
    detect_project_type_from_path,
    get_project_output_dir,
)
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import FinishWorkflow


class TestFinishProject(QtTestCase):
    def create_synthetic_image(self, filename: str, bit_depth: int = 8, shape=(64, 64, 3)) -> Path:
        """Create a synthetic image file on disk."""
        target = self.root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if bit_depth == 8:
            arr = np.random.randint(0, 256, shape, dtype=np.uint8)
        elif bit_depth == 16:
            arr = np.random.randint(0, 65536, shape, dtype=np.uint16)
        else:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")

        # imwrite with convertBGR=False since array is already treated as raw
        imwrite(target, arr, bit_depth=bit_depth)
        return target

    def test_finish_project_defaults_and_zero_settings_survival(self):
        proj_file = self.root / f"test{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))

        # Explicit non-defaults and zeroes
        project.denoise_strength = 0.0
        project.star_amount = 0.0
        project.structure_amount = 25.0
        project.detail_amount = 15.0
        project.round_stars_enabled = True
        project.round_stars_amount = 0.0
        project.star_glow_enabled = True
        project.star_glow_amount = 40.0
        project.blend_mode = BLEND_SCREEN
        project.jpeg_quality = 90

        # Serialize and reload
        encoded = jsonpickle.encode(project)
        reloaded = jsonpickle.decode(encoded)

        self.assertIsInstance(reloaded, FinishProject)
        self.assertEqual(reloaded.project_file, str(proj_file))
        self.assertEqual(reloaded.denoise_strength, 0.0)
        self.assertEqual(reloaded.star_amount, 0.0)
        self.assertEqual(reloaded.structure_amount, 25.0)
        self.assertEqual(reloaded.detail_amount, 15.0)
        self.assertTrue(reloaded.round_stars_enabled)
        self.assertEqual(reloaded.round_stars_amount, 0.0)
        self.assertTrue(reloaded.star_glow_enabled)
        self.assertEqual(reloaded.star_glow_amount, 40.0)
        self.assertEqual(reloaded.blend_mode, BLEND_SCREEN)
        self.assertEqual(reloaded.jpeg_quality, 90)

    def test_operation_snapshot_isolates_mutable_artifact_state(self):
        project = FinishProject(project_file=str(self.root / f"snapshot{FINISH_EXT}"))
        source = self.create_synthetic_image("snapshot_source.tif")
        project.set_source_image(source)
        composite = self.create_synthetic_image("snapshot.finish/composite.tif", bit_depth=16)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        snapshot = project.to_finish_config()
        snapshot.artifact_manifest[ROLE_FINISHED_COMPOSITE]["revision"] = -1
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), composite)
        self.assertIsNone(snapshot.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        snapshot.invalidate_results()
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), composite)
        self.assertEqual(project.get_settings(), snapshot.get_settings())

    def test_ensure_default_project(self):
        default_file = self.root / "projects" / f"default{FINISH_EXT}"
        proj = FinishProject.ensure_default_project(str(default_file))
        self.assertTrue(default_file.is_file())
        self.assertIsInstance(proj, FinishProject)

        # Loading again returns the existing instance
        proj2 = FinishProject.ensure_default_project(str(default_file))
        self.assertEqual(proj2.project_file, str(default_file))

    def test_output_directory_resolution_and_artifacts(self):
        proj_file = self.root / "sub" / f"borrego{FINISH_EXT}"
        out_dir = get_project_output_dir(proj_file)
        self.assertEqual(out_dir, self.root / "sub" / "borrego.finish")

        project = FinishProject(project_file=str(proj_file))
        self.assertEqual(project.get_output_dir(), out_dir)
        self.assertEqual(project.get_project_stem(), "borrego")

        self.assertEqual(project.artifact_path(ROLE_SEPARATED_STARLESS), out_dir / "starless.tif")
        self.assertEqual(project.artifact_path(ROLE_SEPARATED_STARS), out_dir / "stars.tif")
        self.assertEqual(project.artifact_path(ROLE_SKY_MASK), out_dir / "sky_mask.png")
        self.assertEqual(project.artifact_path(ROLE_FINISHED_COMPOSITE), out_dir / "composite.tif")

        with self.assertRaises(ValueError):
            project.artifact_path("invalid_role")

    def test_project_relocation_preserves_owned_inputs(self):
        old_dir = self.root / "old"
        old_file = old_dir / f"shoot{FINISH_EXT}"
        project = FinishProject(project_file=str(old_file))
        source = self.create_synthetic_image("old/shoot.finish/source.tif", bit_depth=16)
        project.set_source_image(source)
        project.source_snapshot_path = str(source)
        mask = self.create_synthetic_image("old/shoot.finish/sky_mask.png")
        project.record_artifact(ROLE_SKY_MASK, mask)
        app = self.make_app(project)
        app.workflow.save_project()

        new_dir = self.root / "moved"
        shutil.move(str(old_dir), str(new_dir))
        app.loadProject(str(new_dir / old_file.name))
        moved = app.project
        self.assertEqual(Path(moved.source_file.path), new_dir / "shoot.finish/source.tif")
        self.assertEqual(moved.source_snapshot_path, moved.source_file.path)
        self.assertTrue(moved.source_is_current())
        self.assertEqual(moved.current_artifact_path(ROLE_SKY_MASK), new_dir / "shoot.finish/sky_mask.png")
        output = app.workflow.do_export_composite()
        self.assertEqual(cv2.imread(str(output), cv2.IMREAD_UNCHANGED).dtype, np.uint16)

    def test_save_as_preserves_existing_read_only_inputs(self):
        project = FinishProject(project_file=str(self.root / f"old{FINISH_EXT}"))
        source = self.create_synthetic_image("old.finish/source.tif")
        project.set_source_image(source)
        mask = self.create_synthetic_image("external/mask.png")
        project.record_artifact(ROLE_SKY_MASK, mask)
        project.relocate(str(self.root / f"new{FINISH_EXT}"))
        self.assertEqual(Path(project.source_file.path), source)
        self.assertTrue(project.source_is_current())
        self.assertEqual(project.current_artifact_path(ROLE_SKY_MASK), mask)

    def test_probe_source_image(self):
        jpg_path = self.create_synthetic_image("test_8.jpg", bit_depth=8, shape=(100, 150, 3))
        self.assertEqual(probe_source_image(jpg_path), 8)

        tif8_path = self.create_synthetic_image("test_8.tif", bit_depth=8, shape=(120, 80, 3))
        self.assertEqual(probe_source_image(tif8_path), 8)

        tif16_path = self.create_synthetic_image("test_16.tiff", bit_depth=16, shape=(200, 300, 3))
        self.assertEqual(probe_source_image(tif16_path), 16)

        png_path = self.create_synthetic_image("unsupported.png", bit_depth=8)
        with self.assertRaisesRegex(ValueError, "JPEG and TIFF"):
            probe_source_image(png_path)

        # Nonexistent file
        with self.assertRaises(FileNotFoundError):
            probe_source_image(self.root / "nonexistent.jpg")

    def test_source_matching_export_policy(self):
        # 1. 8-bit JPEG source -> exports 8-bit JPEG
        jpg_source = self.create_synthetic_image("night.jpg", bit_depth=8)
        proj_file = self.root / f"night_proj{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        app = self.make_app(project)
        workflow = FinishWorkflow(app)

        workflow.do_import_source(jpg_source)
        self.assertEqual(project.source_bit_depth, 8)
        self.assertTrue(project.get_default_export_path().name.endswith(".jpg"))

        exported_jpg = workflow.do_export_composite()
        self.assertTrue(exported_jpg.is_file())
        self.assertTrue(exported_jpg.name.endswith(".jpg"))
        decoded_jpg = cv2.imread(str(exported_jpg), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded_jpg.dtype, np.uint8)

        with self.assertRaisesRegex(ValueError, "format must match"):
            workflow.do_export_composite(self.root / "wrong.tif")
        self.assertTrue(workflow.do_export_composite(self.root / "alias.jpeg").is_file())
        with self.assertRaisesRegex(ValueError, "original source"):
            workflow.do_export_composite(jpg_source)

        # 2. 8-bit TIFF source -> exports 8-bit TIFF
        tif8_source = self.create_synthetic_image("night8.tif", bit_depth=8)
        workflow.do_replace_source(tif8_source)
        self.assertEqual(project.source_bit_depth, 8)
        self.assertTrue(project.get_default_export_path().name.endswith(".tif"))

        exported_tif8 = workflow.do_export_composite()
        self.assertTrue(exported_tif8.is_file())
        decoded_tif8 = cv2.imread(str(exported_tif8), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded_tif8.dtype, np.uint8)

        with self.assertRaisesRegex(ValueError, "format must match"):
            workflow.do_export_composite(self.root / "wrong.jpg")

        # 3. 16-bit TIFF source -> exports 16-bit TIFF
        tif16_source = self.create_synthetic_image("night16.tif", bit_depth=16)
        workflow.do_replace_source(tif16_source)
        self.assertEqual(project.source_bit_depth, 16)
        self.assertTrue(project.get_default_export_path().name.endswith(".tif"))

        exported_tif16 = workflow.do_export_composite()
        self.assertTrue(exported_tif16.is_file())
        decoded_tif16 = cv2.imread(str(exported_tif16), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded_tif16.dtype, np.uint16)

        # 4. Incompatible depth: 16-bit JPEG export must be rejected
        with self.assertRaises(ValueError):
            workflow.do_export_composite(output_path=self.root / "fail.jpg")

    def test_three_mode_routing_and_legacy_loading(self):
        st_file = self.root / "sample.proj_startrails"
        dn_file = self.root / "sample.proj_denoise"
        fn_file = self.root / f"sample{PT_FINISH_EXT}"

        st_proj = Project(projectFile=str(st_file))
        dn_proj = DenoiseProject(project_file=str(dn_file))
        fn_proj = FinishProject(project_file=str(fn_file))

        st_file.write_text(jsonpickle.encode(st_proj), encoding="utf-8")
        dn_file.write_text(jsonpickle.encode(dn_proj), encoding="utf-8")
        fn_file.write_text(jsonpickle.encode(fn_proj), encoding="utf-8")

        # detect_project_type_from_path
        self.assertEqual(detect_project_type_from_path(st_file), TYPE_STARTRAILS)
        self.assertEqual(detect_project_type_from_path(dn_file), TYPE_DENOISE)
        self.assertEqual(detect_project_type_from_path(fn_file), TYPE_FINISH)

        # detect_project_type
        self.assertEqual(detect_project_type(st_proj), TYPE_STARTRAILS)
        self.assertEqual(detect_project_type(dn_proj), TYPE_DENOISE)
        self.assertEqual(detect_project_type(fn_proj), TYPE_FINISH)
        self.assertEqual(detect_project_type(st_file), TYPE_STARTRAILS)
        self.assertEqual(detect_project_type(dn_file), TYPE_DENOISE)
        self.assertEqual(detect_project_type(fn_file), TYPE_FINISH)

        # app routing
        app = self.make_app()
        app.loadProject(str(st_file))
        self.assertEqual(app.workflow.mode_name, "startrails")
        self.assertIsInstance(app.project, Project)

        app.loadProject(str(dn_file))
        self.assertEqual(app.workflow.mode_name, "denoise")
        self.assertIsInstance(app.project, DenoiseProject)

        app.loadProject(str(fn_file))
        self.assertEqual(app.workflow.mode_name, "finish")
        self.assertIsInstance(app.project, FinishProject)

        # newProject routing
        new_fn = str(self.root / f"brand_new{PT_FINISH_EXT}")
        app.newProject(new_fn)
        self.assertEqual(app.workflow.mode_name, "finish")
        self.assertIsInstance(app.project, FinishProject)

        # Legacy project.json
        legacy_file = self.root / "legacy.project.json"
        legacy_file.write_text(jsonpickle.encode(st_proj), encoding="utf-8")
        app.loadProject(str(legacy_file))
        self.assertEqual(app.workflow.mode_name, "startrails")

        # XML rejection
        xml_file = self.root / "invalid.xml"
        xml_file.write_text("<project></project>", encoding="utf-8")
        with self.assertRaises(UnsupportedProjectError):
            app.loadProject(str(xml_file))

    def test_finish_view_sidebar_and_canvas_shell(self):
        proj_file = self.root / f"view_test{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        app = self.make_app(project)

        shell = QObject()
        shell.canvas_main = CanvasLabel()
        self.addCleanup(shell.deleteLater)

        view = FinishView(app, shell)
        self.addCleanup(view.teardown)

        sidebar = view.build_sidebar(shell.canvas_main)
        self.assertIsInstance(sidebar, SidebarFinish)
        sidebar.show()

        view.bind()
        view.resetProjectView()

        # Initial state: no source image loaded
        self.assertTrue(sidebar.btn_replace_source.isHidden())
        self.assertFalse(sidebar.btn_import_source.isHidden())
        self.assertEqual(sidebar.skyCard._status, "locked")
        self.assertEqual(sidebar.separateCard._status, "locked")
        self.assertEqual(sidebar.starlessCard._status, "locked")
        self.assertEqual(sidebar.starsCard._status, "locked")
        self.assertEqual(sidebar.recombineCard._status, "locked")
        self.assertTrue(shell.canvas_main.pixmap.isNull())

        # Import a source image
        img_path = self.create_synthetic_image("imported.jpg", bit_depth=8, shape=(80, 100, 3))
        app.workflow.do_import_source(img_path)
        view.resetProjectView()

        # Canvas receives pixmap
        self.assertIsNotNone(shell.canvas_main.pixmap)
        self.assertEqual(shell.canvas_main.pixmap.width(), 100)
        self.assertEqual(shell.canvas_main.pixmap.height(), 80)

        self.assertIn("100 × 80 px", sidebar.lbl_source_meta.text())
        self.assertNotIn("source_dimensions", project.__getstate__())
        self.assertNotIn("source_format", project.__getstate__())

        # Step 1 is ready, Step 2 remains locked until mask is defined
        self.assertEqual(sidebar.skyCard._status, "ready")
        self.assertEqual(sidebar.separateCard._status, "locked")
        self.assertFalse(sidebar.btn_replace_source.isHidden())
        self.assertTrue(sidebar.btn_import_source.isHidden())

        # Simulate sky mask defined
        mask_path = project.get_output_dir() / "sky_mask.png"
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        imwrite(mask_path, np.ones((80, 100), dtype=np.uint8) * 255, bit_depth=8)
        project.record_artifact(ROLE_SKY_MASK, mask_path)
        view.updateReadyStates()

        self.assertEqual(sidebar.separateCard._status, "ready")
        self.assertEqual(sidebar.starlessCard._status, "locked")

        # Simulate stars separated
        starless_path = project.artifact_path(ROLE_SEPARATED_STARLESS)
        stars_path = project.artifact_path(ROLE_SEPARATED_STARS)
        imwrite(starless_path, np.zeros((80, 100, 3), dtype=np.uint16), bit_depth=16)
        imwrite(stars_path, np.zeros((80, 100, 3), dtype=np.uint16), bit_depth=16)
        project.record_artifact(ROLE_SEPARATED_STARLESS, starless_path)
        project.record_artifact(ROLE_SEPARATED_STARS, stars_path)
        view.updateReadyStates()

        self.assertEqual(sidebar.separateCard._status, "done")
        self.assertEqual(sidebar.starlessCard._status, "ready")
        self.assertEqual(sidebar.starsCard._status, "ready")
        self.assertEqual(sidebar.recombineCard._status, "ready")

        # Output files list in sidebar shows published artifacts
        outputs = app.workflow.get_output_file_list()
        self.assertGreaterEqual(len(outputs), 2)
        sidebar.outputFiles.set_files(outputs)
        self.assertEqual(len(sidebar.outputFiles.model.files), len(outputs))

        self.create_synthetic_image("imported.jpg", shape=(40, 60, 3))
        app.workflow.do_replace_source(img_path)
        view.resetProjectView()
        self.assertEqual(shell.canvas_main.pixmap.width(), 60)
        self.assertIn("60 × 40 px", sidebar.lbl_source_meta.text())
        self.assertEqual(sidebar.separateCard._status, "locked")
        self.assertEqual(sidebar.outputFiles.model.files, [])
        img_path.unlink()
        view.resetProjectView()
        self.assertTrue(shell.canvas_main.pixmap.isNull())
        self.assertFalse(sidebar.btn_save_output.isEnabled())

    def test_artifact_freshness_and_source_replacement(self):
        project = FinishProject(project_file=str(self.root / f"fresh{FINISH_EXT}"))
        app = self.make_app(project)
        source = self.create_synthetic_image("first.tif")
        app.workflow.do_import_source(source)
        composite = project.artifact_path(ROLE_FINISHED_COMPOSITE)
        composite.parent.mkdir(parents=True, exist_ok=True)
        imwrite(composite, np.zeros((64, 64, 3), dtype=np.uint16), bit_depth=16)
        # Existing files are not published just because they use a default filename.
        self.assertEqual(app.workflow.get_output_file_list(), [])
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        self.assertEqual(len(app.workflow.get_output_file_list()), 1)
        app.workflow.save_project()
        app.loadProject(project.project_file)
        project = app.project
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), composite)
        result = app.workflow.do_export_composite()
        self.assertFalse(cv2.imread(str(result), cv2.IMREAD_UNCHANGED).any())

        stamp = composite.stat()
        os.utime(composite, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        replacement = self.create_synthetic_image("second.tif")
        app.workflow.do_replace_source(replacement)
        self.assertTrue(composite.is_file())
        self.assertIsNone(project.composite_path)
        self.assertEqual(app.workflow.get_output_file_list(), [])
        result = app.workflow.do_export_composite()
        np.testing.assert_array_equal(
            cv2.imread(str(result), cv2.IMREAD_UNCHANGED),
            cv2.imread(str(replacement), cv2.IMREAD_UNCHANGED),
        )
        stamp = replacement.stat()
        os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000))
        self.assertFalse(project.source_is_current())
        self.assertEqual(app.workflow.get_output_file_list(), [])
        with self.assertRaisesRegex(ValueError, "Source image changed"):
            app.workflow.do_export_composite()

    def test_project_overlay_recent_tag_and_signals(self):
        from startrails.ui.project_overlay import ProjectWelcomeOverlay
        from startrails.lib.recent import add_recent_project

        fn_file = self.root / f"recent_test{FINISH_EXT}"
        fn_file.touch()
        add_recent_project(fn_file)

        overlay = ProjectWelcomeOverlay()
        self.addCleanup(overlay.deleteLater)
        overlay.refresh_recent_projects()

        items = [overlay.combo_recent.itemText(i) for i in range(overlay.combo_recent.count())]
        self.assertTrue(any(item.startswith("[Finish]") and fn_file.name in item for item in items))

        create_fired = []
        open_fired = []
        overlay.createFinishRequested.connect(lambda: create_fired.append(True))
        overlay.openFinishRequested.connect(lambda: open_fired.append(True))

        overlay.btn_fn_new.click()
        overlay.btn_fn_open.click()
        self.assertEqual(len(create_fired), 1)
        self.assertEqual(len(open_fired), 1)
