"""Persistence, migration, configuration ownership, and cache invalidation."""

from pathlib import Path

import jsonpickle
import numpy as np

from support import IsolatedTestCase
from startrails.app import App
from startrails.lib.project import Project
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.op.denoise.compose_horizon import ComposeHorizon
from startrails.lib.file import InputFile
from startrails.op.denoise.align_stars import AlignStars
from startrails.op.denoise.refine_mask import RefineMask


class ProjectTests(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.project = DenoiseProject(str(self.root / "first.proj_denoise"))
        self.app = self.make_app(self.project)

    def test_session_cancellation_survives_starting_the_next_stage(self):
        output = self.root / "cancelled-mask.png"
        with self.app.workflow.operation_session():
            first = self.app.workflow._new_operation(AlignStars)
            first.startJob(1)
            first.requestInterrupt()
            second = self.app.workflow._new_operation(RefineMask)
            result = second.refine(
                np.zeros((8, 8, 3), np.float32),
                np.ones((8, 8), np.float32),
                search_radius=3,
                erosion_pixels=0,
                foliage_protection=False,
                export_path=output,
            )
        self.assertIsNone(result)
        self.assertFalse(output.exists())

    def test_startrail_sorting_uses_timestamps_across_camera_counter_rollover(self):
        app = self.make_app()
        earlier = InputFile("DSC09999.JPG", "DSC09999.JPG", timestamp=1000)
        later = InputFile("DSC00001.JPG", "DSC00001.JPG", timestamp=2000)
        app.project.rawInputFiles = [later, earlier]
        app.sortInputFiles(sortBy="date", sortOrder="asc")
        self.assertEqual(app.project.rawInputFiles, [earlier, later])
        app.sortInputFiles(sortBy="name", sortOrder="asc")
        self.assertEqual(app.project.rawInputFiles, [later, earlier])

    def test_explicit_zero_and_disabled_settings_survive_reload_and_processing(self):
        self.project.horizon_blend_percent = 0
        self.project.denoise_horizon_band = False
        self.project.use_gpu = False
        self.project.sigma_clip_threshold = 2.3
        self.app.saveProject()
        self.app.loadProject(self.project.project_file)
        config = self.app.project.to_denoise_config()
        self.assertEqual(config.horizon_blend_percent, 0)
        self.assertFalse(config.denoise_horizon_band)
        self.assertFalse(config.use_gpu)
        self.assertEqual(config.sigma_clip_threshold, 2.3)
        sky = np.full((12, 12, 3), 0.8, np.float32)
        ground = np.full_like(sky, 0.2)
        mask = np.ones(sky.shape[:2], np.float32)
        compositor = HorizonCompositor(sky, ground, mask, mask, feather_radius=0)
        result, path = ComposeHorizon().compose(compositor, config, write_output=False)
        np.testing.assert_allclose(result, sky, atol=1e-7, rtol=0)
        self.assertIsNone(path)

    def test_legacy_ui_project_deserialization(self):
        legacy_json = """{
            "py/object": "startrails.ui.project.Project",
            "py/state": {
                "rawInputFiles": [],
                "outputFiles": [],
                "selected": null,
                "operations": {},
                "projectFile": "projects/test.project.json"
            }
        }"""
        decoded = jsonpickle.decode(legacy_json)
        self.assertIsInstance(decoded, Project)
        self.assertEqual(decoded.projectFile, "projects/test.project.json")

    def test_project_type_detection(self):
        from startrails.lib.project_type import (
            detect_project_type,
            detect_project_type_from_path,
            UnsupportedProjectError,
            InvalidProjectError,
            TYPE_STARTRAILS,
            TYPE_DENOISE,
        )

        # Extension checks
        self.assertEqual(detect_project_type_from_path("foo.proj_startrails"), TYPE_STARTRAILS)
        self.assertEqual(detect_project_type_from_path("foo.project.json"), TYPE_STARTRAILS)
        self.assertEqual(detect_project_type_from_path("foo.proj_denoise"), TYPE_DENOISE)
        with self.assertRaises(UnsupportedProjectError):
            detect_project_type_from_path("foo.xml")

        # Object checks
        p_st = Project()
        p_dn = DenoiseProject()
        self.assertEqual(detect_project_type(p_st), TYPE_STARTRAILS)
        self.assertEqual(detect_project_type(p_dn), TYPE_DENOISE)

        # File content checks
        f_st = self.root / "shoot.proj_startrails"
        f_st.write_text(jsonpickle.encode(p_st))
        self.assertEqual(detect_project_type(f_st), TYPE_STARTRAILS)

        f_dn = self.root / "stars.proj_denoise"
        f_dn.write_text(jsonpickle.encode(p_dn))
        self.assertEqual(detect_project_type(f_dn), TYPE_DENOISE)

        # XML file rejection
        f_xml = self.root / "legacy_pyquator.xml"
        f_xml.write_text('<?xml version="1.0"?><project name="test"></project>')
        with self.assertRaises(UnsupportedProjectError):
            detect_project_type(f_xml)

        # Corrupt JSON rejection
        f_bad = self.root / "corrupt.json"
        f_bad.write_text("NOT VALID JSON {{{")
        with self.assertRaises(InvalidProjectError):
            detect_project_type(f_bad)

    def test_output_directory_resolver(self):
        from startrails.lib.project_type import get_project_output_dir

        # 1. Legacy project.json -> name.project
        legacy_file = self.root / "borrego.project.json"
        self.assertEqual(get_project_output_dir(legacy_file), self.root / "borrego.project")

        # 2. Fresh proj_startrails -> name
        st_file = self.root / "borrego.proj_startrails"
        self.assertEqual(get_project_output_dir(st_file), self.root / "borrego")

        # 3. Existing legacy directory next to proj_startrails -> preserves legacy dir
        legacy_dir = self.root / "borrego.project"
        legacy_dir.mkdir()
        self.assertEqual(get_project_output_dir(st_file), legacy_dir)

        # 4. Fresh proj_denoise -> name.denoise (prevents collisions with startrails projects)
        dn_file = self.root / "night_sky.proj_denoise"
        self.assertEqual(get_project_output_dir(dn_file), self.root / "night_sky.denoise")

        # 5. Method calls on project objects
        p_st = Project(projectFile=str(st_file))
        self.assertEqual(p_st.get_output_dir(), legacy_dir)

        p_dn = DenoiseProject(projectFile=str(dn_file))
        self.assertEqual(p_dn.get_output_dir(), self.root / "night_sky.denoise")

        # 6. Verify identical basenames do NOT collide
        st_same_base = self.root / "desert.proj_startrails"
        dn_same_base = self.root / "desert.proj_denoise"
        st_out = get_project_output_dir(st_same_base)
        dn_out = get_project_output_dir(dn_same_base)
        self.assertEqual(st_out, self.root / "desert")
        self.assertEqual(dn_out, self.root / "desert.denoise")
        self.assertNotEqual(st_out, dn_out)

        for extension, output_name in (
            (".PROJ_DENOISE", "NightSky.denoise"),
            (".PrOj_StArTrAiLs", "NightSky"),
            (".PROJECT.JSON", "NightSky.PROJECT"),
            (".JSON", "NightSky"),
        ):
            with self.subTest(extension=extension):
                self.assertEqual(
                    get_project_output_dir(self.root / f"NightSky{extension}"),
                    self.root / output_name,
                )
        for extension, legacy_name in (
            (".PROJ_DENOISE", "NightSky.denoise.project"),
            (".PROJ_STARTRAILS", "NightSky.project"),
        ):
            with self.subTest(legacy=extension):
                legacy_path = self.root / legacy_name
                legacy_path.mkdir()
                self.assertEqual(get_project_output_dir(self.root / f"NightSky{extension}"), legacy_path)

    def test_load_project_authoritative_path_and_no_overwrite_on_error(self):
        from startrails.lib.project_type import UnsupportedProjectError, InvalidProjectError

        app = App.__new__(App)
        app.activeOperation = None
        app.state = {}
        app.stateFile = str(self.root / "app.json")

        orig_file = self.root / "original.proj_startrails"
        orig_proj = Project(projectFile=str(orig_file))
        orig_file.write_text(jsonpickle.encode(orig_proj, indent=2))

        # Copy to copy.proj_startrails (it still has projectFile pointing to original)
        copy_file = self.root / "copy.proj_startrails"
        copy_file.write_text(orig_file.read_text())

        # Load copy_file
        app.loadProject(str(copy_file))
        # The chosen Open path MUST be authoritative
        self.assertEqual(app.project.projectFile, str(copy_file))

        # Modify and save
        app.project.sortBy = "name"
        app.saveProject()

        # Original file should NOT have been modified
        reloaded_orig = jsonpickle.decode(orig_file.read_text())
        self.assertEqual(reloaded_orig.sortBy, "date")

        # Copy file SHOULD have been updated
        reloaded_copy = jsonpickle.decode(copy_file.read_text())
        self.assertEqual(reloaded_copy.sortBy, "name")

        # Error handling: unsupported XML must not modify file or active project
        xml_file = self.root / "unsupported.xml"
        xml_content = '<?xml version="1.0"?><project></project>'
        xml_file.write_text(xml_content)

        active_before = app.project
        with self.assertRaises(UnsupportedProjectError):
            app.loadProject(str(xml_file))

        self.assertIs(app.project, active_before)
        self.assertEqual(xml_file.read_text(), xml_content)

        # Error handling: corrupt JSON must not modify file or active project
        corrupt_file = self.root / "corrupt.proj_startrails"
        corrupt_content = "INVALID { JSON"
        corrupt_file.write_text(corrupt_content)

        with self.assertRaises(InvalidProjectError):
            app.loadProject(str(corrupt_file))

        self.assertIs(app.project, active_before)
        self.assertEqual(corrupt_file.read_text(), corrupt_content)

    def test_default_reference_tracks_middle_and_preserves_manual_choice(self):
        paths = [str(self.root / f"star{i}.tif") for i in range(7)]
        workflow = self.app.workflow
        workflow.add_star_files(paths[:4])
        self.assertIs(workflow.get_reference_file(), self.project.star_files[2])
        self.assertIsNone(self.project.reference_file)
        self.assertEqual([f.is_reference for f in self.project.star_files], [False, False, True, False])
        self.project.mask_invalidated = False
        workflow.add_star_files(paths[4:7])
        self.assertIs(workflow.get_reference_file(), self.project.star_files[3])
        self.assertTrue(self.project.mask_invalidated)
        selected = self.project.star_files[0]
        workflow.set_reference_file(selected)
        self.project.mask_invalidated = False
        workflow.add_star_files([str(self.root / "another.tif")])
        self.assertIs(workflow.get_reference_file(), selected)
        self.assertFalse(self.project.mask_invalidated)
        workflow.remove_star_file(selected)
        self.assertIs(workflow.get_reference_file(), self.project.star_files[3])
        self.assertTrue(self.project.mask_invalidated)
        workflow.add_star_files(paths[:5], clear=True)
        self.assertIs(workflow.get_reference_file(), self.project.star_files[2])
        import jsonpickle

        restored = jsonpickle.decode(jsonpickle.encode(self.project))
        self.assertIs(restored.get_reference_file(), restored.star_files[2])
        self.assertEqual(restored.to_denoise_config().base_image, Path(paths[2]))

    def test_manually_choosing_the_automatic_middle_pins_it(self):
        paths = [str(self.root / f"star{i}.tif") for i in range(5)]
        self.app.workflow.add_star_files(paths[:3])
        middle = self.project.star_files[1]
        self.assertIs(self.project.get_reference_file(), middle)
        self.project.mask_invalidated = False
        self.app.workflow.set_reference_file(middle)
        self.assertIs(self.project.reference_file, middle)
        self.assertFalse(self.project.mask_invalidated)
        self.app.workflow.add_star_files(paths[3:])
        self.assertIs(self.project.get_reference_file(), middle)
        self.assertFalse(self.project.mask_invalidated)

    def test_reference_and_dark_changes_invalidate_transforms(self):
        self.app.workflow.add_star_files(["first.tif", "second.tif"])
        self.project.homographies = {"first.tif": np.eye(3)}
        self.app.workflow.set_reference_file(self.project.star_files[0])
        self.assertEqual(self.project.homographies, {})
        self.assertTrue(self.project.mask_invalidated)
        self.project.homographies = {"second.tif": np.eye(3)}
        self.app.workflow.add_noise_files(["dark.tif"])
        self.assertEqual(self.project.homographies, {})

    def test_changed_inputs_and_sidecars_reject_cached_stacks(self):
        source = self.root / "source.tif"
        source.write_bytes(b"source")
        self.app.workflow.add_star_files([str(source)])
        for name in ("sky_stack_path", "ground_stack_path"):
            path = self.root / (name + ".tif")
            path.write_bytes(b"stack")
            setattr(self.project, name, str(path))
        self.project.record_stacks()
        self.assertTrue(self.project.stacks_are_current())
        Path(self.project.sky_stack_path).write_bytes(b"changed stack")
        self.assertFalse(self.project.stacks_are_current())
        self.project.record_stacks()
        source.write_bytes(b"changed source")
        self.assertFalse(self.project.stacks_are_current())

    def test_config_does_not_share_mutable_transform_arrays(self):
        self.project.homographies = {"first.tif": np.eye(3)}
        config = self.project.to_denoise_config()
        config.homographies[Path("first.tif").resolve()][0, 0] = 2
        self.assertEqual(self.project.homographies["first.tif"][0, 0], 1)

    def test_copy_rebases_writable_artifacts_and_keeps_imported_mask(self):
        original_dir = self.project.get_output_dir()
        self.project.sky_stack_path = str(original_dir / "sky_stack.tif")
        self.project.output_path = str(original_dir / "first.tif")
        imported = self.root / "imported.png"
        imported.write_bytes(b"mask")
        self.project.mask_path = str(imported)
        self.project.relocate(str(self.root / "copy.proj_denoise"))
        config = self.project.to_denoise_config()
        self.assertEqual(config.sky_stack_path.parent, self.project.get_output_dir())
        self.assertEqual(config.output_path.parent, self.project.get_output_dir())
        self.assertEqual(config.mask_path, imported)

    def test_legacy_median_projects_preserve_the_previous_mean_algorithm(self):
        import jsonpickle

        self.project.stack_method = "median"
        restored = jsonpickle.decode(jsonpickle.encode(self.project))
        self.assertEqual(restored.stack_method, "mean")

    def test_missing_mask_is_actionable_instead_of_full_sky(self):
        self.project.mask_path = str(self.root / "missing.png")
        with self.assertRaisesRegex(FileNotFoundError, "Sky mask is missing"):
            self.app.workflow.get_config()
