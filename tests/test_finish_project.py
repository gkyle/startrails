"""Unit tests for Finish project persistence, source I/O, export policy, and mode routing."""

from pathlib import Path
from dataclasses import replace
import copy
import json
import os
import shutil
import cv2
import jsonpickle
import numpy as np
from PySide6.QtCore import QObject

from support import QtTestCase
from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.defaults import (
    BLEND_SCREEN,
    FINISH_DEFAULTS,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    ROLE_SOURCE_SNAPSHOT,
    ROLE_UNMASKED_STARLESS,
    RETIRED_FINISH_SETTING_NAMES,
)
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.image_io import imwrite
from startrails.lib.project_startrails import Project
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
        rng = np.random.default_rng(42)
        if bit_depth == 8:
            arr = rng.integers(0, 256, shape, dtype=np.uint8)
        elif bit_depth == 16:
            arr = rng.integers(0, 65536, shape, dtype=np.uint16)
        else:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")

        # imwrite with convertBGR=False since array is already treated as raw
        imwrite(target, arr, bit_depth=bit_depth)
        return target

    def register_composite_fixture(self, project: FinishProject, *, bit_depth: int, value: int) -> Path:
        """Publish a composite whose pixels cannot be mistaken for the source image."""
        target = project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True)
        dtype = np.uint8 if bit_depth == 8 else np.uint16
        shape = (*project.get_source_dimensions(), 3)
        pixels = np.full(shape, value / np.iinfo(dtype).max, dtype=np.float32)
        imwrite(target, pixels, bit_depth=16)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, target)
        return target

    def assert_no_composite_export_rejected(self, workflow: FinishWorkflow, output_path: Path) -> None:
        with self.assertRaisesRegex(ValueError, "No current composite"):
            workflow.do_export_composite(output_path)
        self.assertFalse(output_path.exists())

    def test_exports_protect_internal_images_and_avoid_default_name_collisions(self):
        source = self.create_synthetic_image("export_source.tif", bit_depth=8)
        roles = (
            ROLE_SOURCE_SNAPSHOT,
            ROLE_UNMASKED_STARLESS,
            ROLE_SEPARATED_STARLESS,
            ROLE_SEPARATED_STARS,
            ROLE_FINISHED_COMPOSITE,
        )
        for role in roles:
            with self.subTest(role=role):
                project = FinishProject(project_file=str(self.root / f"{role}{FINISH_EXT}"))
                # Use the actual reserved filename as the project stem.
                stem = project.artifact_path(role).stem
                project.project_file = str(self.root / f"{stem}{FINISH_EXT}")
                app = self.make_app(project)
                workflow = FinishWorkflow(app)
                project.set_source_image(source)
                reserved = project.artifact_path(role, for_write=True)
                self.assertNotEqual(project.get_default_export_path(), reserved)
                reserved.parent.mkdir(parents=True, exist_ok=True)
                imwrite(reserved, np.full((64, 64, 3), 12345, dtype=np.uint16), bit_depth=16)
                project.record_artifact(role, reserved)
                self.register_composite_fixture(project, bit_depth=8, value=100)
                original_bytes = reserved.read_bytes()
                with self.assertRaisesRegex(ValueError, "must not overwrite"):
                    workflow.do_export_composite(reserved)
                exported = workflow.do_export_composite()
                self.assertEqual(cv2.imread(str(exported), cv2.IMREAD_UNCHANGED).dtype, np.uint8)
                self.assertEqual(reserved.read_bytes(), original_bytes)
                self.assertEqual(project.current_artifact_path(role), reserved)

        # Referenced artifacts outside the owned directory are protected too.
        external = self.create_synthetic_image("external_starless.tif", bit_depth=16)
        project.record_artifact(ROLE_SEPARATED_STARLESS, external)
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            workflow.do_export_composite(external)
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            workflow.do_export_composite(source)

    def test_finish_project_defaults_and_zero_settings_survival(self):
        proj_file = self.root / f"test{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        self.assertEqual(project.structure_amount, 20.0)
        self.assertEqual(project.detail_amount, 20.0)

        # Explicit non-defaults and zeroes
        project.denoise_strength = 0.0
        project.star_amount = 0.0
        project.structure_amount = 25.0
        project.detail_amount = 15.0
        project.blend_mode = BLEND_SCREEN
        project.jpeg_quality = 90
        project.nox_stride = 128
        project.chroma_postfilter = False

        # Serialize and reload
        encoded = jsonpickle.encode(project)
        reloaded = jsonpickle.decode(encoded)

        self.assertIsInstance(reloaded, FinishProject)
        self.assertEqual(reloaded.project_file, str(proj_file))
        self.assertEqual(reloaded.denoise_strength, 0.0)
        self.assertEqual(reloaded.star_amount, 0.0)
        self.assertEqual(reloaded.structure_amount, 25.0)
        self.assertEqual(reloaded.detail_amount, 15.0)
        self.assertEqual(reloaded.blend_mode, BLEND_SCREEN)
        self.assertEqual(reloaded.jpeg_quality, 90)
        self.assertEqual(reloaded.nox_stride, 128)
        self.assertFalse(reloaded.chroma_postfilter)

        # Authoritative defaults have one owner; Stars Amount and blend mode
        # are the only star-layer controls.
        self.assertEqual(FINISH_DEFAULTS.star_amount, 100.0)
        self.assertEqual(FINISH_DEFAULTS.blend_mode, "add")
        self.assertTrue(FINISH_DEFAULTS.chroma_postfilter)
        self.assertTrue(FINISH_DEFAULTS.enable_starless_denoise)
        self.assertTrue(FINISH_DEFAULTS.enable_starless_sharpen)
        self.assertIn("enable_starless_finishing", RETIRED_FINISH_SETTING_NAMES)
        self.assertFalse(set(RETIRED_FINISH_SETTING_NAMES) & set(FINISH_DEFAULTS.__dataclass_fields__))
        for removed in RETIRED_FINISH_SETTING_NAMES:
            self.assertNotIn(removed, FINISH_DEFAULTS.__dataclass_fields__)

    def test_old_projects_drop_retired_settings_and_inherit_new_defaults(self):
        project = FinishProject(project_file=str(self.root / f"legacy{FINISH_EXT}"))
        encoded = jsonpickle.encode(project)
        state = json.loads(encoded)
        persisted = state["py/state"]
        for name in RETIRED_FINISH_SETTING_NAMES:
            persisted[name] = "retired-value"
        for name in ("star_amount", "blend_mode"):
            persisted.pop(name, None)

        reloaded = jsonpickle.decode(json.dumps(state))

        self.assertIsInstance(reloaded, FinishProject)
        for name in RETIRED_FINISH_SETTING_NAMES:
            self.assertFalse(hasattr(reloaded, name), name)
        self.assertEqual(reloaded.star_amount, FINISH_DEFAULTS.star_amount)
        self.assertEqual(reloaded.blend_mode, FINISH_DEFAULTS.blend_mode)

    def test_legacy_load_discards_star_effect_records_and_only_owned_caches(self):
        proj_file = self.root / f"effects_legacy{FINISH_EXT}"
        output_dir = get_project_output_dir(proj_file)
        output_dir.mkdir(parents=True)
        project = FinishProject(project_file=str(proj_file))
        state = json.loads(jsonpickle.encode(project))
        persisted = state["py/state"]

        owned_catalog = output_dir / "catalog.npz"
        owned_finished = output_dir / "finished_stars.tif"
        owned_catalog.write_bytes(b"owned catalog")
        owned_finished.write_bytes(b"owned finished stars")

        external_dir = self.root / "external"
        external_dir.mkdir()
        external_round = external_dir / "round_delta.npz"
        external_finished = external_dir / "finished_stars.tif"
        external_round.write_bytes(b"external round")
        external_finished.write_bytes(b"external finished")
        # The canonical cache name is a symlink to an external file: never follow it.
        (output_dir / "round_delta.npz").symlink_to(external_round)

        persisted["star_catalog_path"] = str(owned_catalog)
        persisted["round_delta_path"] = str(external_round)
        persisted["finished_stars_path"] = str(external_finished)
        persisted["composite_path"] = str(output_dir / "composite.tif")
        persisted["final_output_path"] = str(self.root / "export.tif")
        persisted["composite_signature"] = "legacy-composite"
        for role in ("star_catalog", "round_delta", "finished_stars"):
            persisted["artifact_manifest"][role] = {
                "source": [1, [0, 1]],
                "file": [0, 1],
                "revision": 0,
                "options": {},
            }
        for role in ("finished_composite", "export"):
            persisted["artifact_manifest"][role] = {
                "source": [1, [0, 1]],
                "file": [0, 1],
                "revision": 0,
                "options": {},
            }

        proj_file.write_text(json.dumps(state), encoding="utf-8")

        # Decoding (as type detection and recent-project listing do) drops the
        # records but must not delete files.
        reloaded = jsonpickle.decode(json.dumps(state))
        self.assertEqual(detect_project_type_from_path(proj_file), TYPE_FINISH)
        self.assertTrue(owned_catalog.exists())
        self.assertTrue(owned_finished.exists())
        for role in ("star_catalog", "round_delta", "finished_stars", "finished_composite", "export"):
            self.assertNotIn(role, reloaded.artifact_manifest)
        self.assertIsNone(reloaded.composite_path)
        self.assertIsNone(reloaded.final_output_path)
        self.assertIsNone(reloaded.composite_signature)
        for field in ("star_catalog_path", "round_delta_path", "finished_stars_path"):
            self.assertFalse(hasattr(reloaded, field), field)

        # Opening the project removes only caches it owns.
        app = self.make_app(FinishProject(project_file=str(self.root / f"active{FINISH_EXT}")))
        app.loadProject(str(proj_file))

        self.assertFalse(owned_catalog.exists())
        self.assertFalse(owned_finished.exists())
        # A symlinked cache is not owned data and its external target is untouched.
        self.assertTrue((output_dir / "round_delta.npz").is_symlink())
        self.assertEqual(external_round.read_bytes(), b"external round")
        self.assertEqual(external_finished.read_bytes(), b"external finished")

        # A symlinked output directory points at external user data. Canonical
        # filenames there are not project-owned; records are dropped but files stay.
        external_output = self.root / "external_output"
        external_output.mkdir()
        external_catalog = external_output / "catalog.npz"
        external_owned_name = external_output / "finished_stars.tif"
        external_catalog.write_bytes(b"external catalog")
        external_owned_name.write_bytes(b"external finished stars")
        symlink_project_file = self.root / f"symlink_effects{FINISH_EXT}"
        symlink_output_dir = get_project_output_dir(symlink_project_file)
        symlink_output_dir.symlink_to(external_output, target_is_directory=True)

        symlink_project = FinishProject(project_file=str(symlink_project_file))
        symlink_state = json.loads(jsonpickle.encode(symlink_project))
        symlink_persisted = symlink_state["py/state"]
        symlink_persisted["round_stars_enabled"] = True
        symlink_persisted["artifact_manifest"]["star_catalog"] = {
            "source": [1, [0, 1]],
            "file": [0, 1],
            "revision": 0,
            "options": {},
        }
        symlink_reloaded = jsonpickle.decode(json.dumps(symlink_state))
        symlink_reloaded.remove_retired_star_effect_caches()

        self.assertTrue(symlink_output_dir.is_symlink())
        self.assertNotIn("star_catalog", symlink_reloaded.artifact_manifest)
        self.assertEqual(external_catalog.read_bytes(), b"external catalog")
        self.assertEqual(external_owned_name.read_bytes(), b"external finished stars")

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

    def test_publish_separation_rejects_stale_revision(self):
        project = FinishProject(project_file=str(self.root / f"publish{FINISH_EXT}"))
        source = self.create_synthetic_image("publish_source.tif")
        project.set_source_image(source)
        starless = self.create_synthetic_image("publish.finish/starless.tif", bit_depth=16)
        stars = self.create_synthetic_image("publish.finish/stars.tif", bit_depth=16)
        revision = project.processing_revision
        self.assertTrue(
            project.publish_separation(
                starless,
                stars,
                signature="signature-a",
                model_identity="model-a",
                expected_revision=revision,
            )
        )
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARLESS))

        # An unrelated invalidation advances the revision but keeps the separation current.
        project.invalidate_artifact_roles({ROLE_FINISHED_COMPOSITE})
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARLESS))

        self.assertFalse(
            project.publish_separation(
                starless,
                stars,
                signature="signature-b",
                model_identity="model-b",
                expected_revision=revision,
            )
        )
        self.assertEqual(project.separation_signature, "signature-a")
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARLESS))

        # A missing optional composite is a caller error: reject it before any
        # staged replacement replaces the current destinations.
        manifest = copy.deepcopy(project.artifact_manifest)
        published_bytes = {
            role: project.current_artifact_path(role).read_bytes()
            for role in (ROLE_SEPARATED_STARLESS, ROLE_SEPARATED_STARS)
        }
        with ArtifactTransaction() as transaction:
            for role in (ROLE_SEPARATED_STARLESS, ROLE_SEPARATED_STARS):
                staged = transaction.stage(project.artifact_path(role, for_write=True))
                Path(staged).write_bytes(f"replacement {role}".encode())
            with self.assertRaises(FileNotFoundError):
                project.publish_separation(
                    starless,
                    stars,
                    signature="signature-c",
                    model_identity="model-c",
                    expected_revision=project.processing_revision,
                    composite_path=self.root / "missing_composite.tif",
                    transaction=transaction,
                )
        for role, content in published_bytes.items():
            self.assertIsNotNone(project.current_artifact_path(role))
            self.assertEqual(project.artifact_path(role).read_bytes(), content)
        self.assertEqual(project.artifact_manifest, manifest)
        self.assertEqual(project.separation_signature, "signature-a")

    def test_export_and_blend_settings_invalidate_only_their_dependents(self):
        project = FinishProject(project_file=str(self.root / f"settings{FINISH_EXT}"))
        source = self.create_synthetic_image("settings_source.tif")
        project.set_source_image(source)
        starless = self.create_synthetic_image("settings.finish/starless.tif", bit_depth=16)
        stars = self.create_synthetic_image("settings.finish/stars.tif", bit_depth=16)
        composite = self.create_synthetic_image("settings.finish/composite.tif", bit_depth=16)
        endpoint = self.create_synthetic_image("settings.finish/denoise_endpoint.tif", bit_depth=16)
        denoised = self.create_synthetic_image("settings.finish/denoised.tif", bit_depth=16)
        finished_starless = self.create_synthetic_image("settings.finish/finished_starless.tif", bit_depth=16)
        export = self.create_synthetic_image("settings.finish/export.tif", bit_depth=16)
        project.record_artifact(ROLE_SEPARATED_STARLESS, starless)
        project.record_artifact(ROLE_SEPARATED_STARS, stars)
        project.record_artifact(ROLE_DENOISE_ENDPOINT, endpoint)
        project.record_artifact(ROLE_DENOISED_STARLESS, denoised)
        project.record_artifact(ROLE_FINISHED_STARLESS, finished_starless)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        project.record_export(export)

        project.update_settings(replace(project.get_settings(), jpeg_quality=90))
        for role in (
            ROLE_SEPARATED_STARLESS,
            ROLE_DENOISE_ENDPOINT,
            ROLE_DENOISED_STARLESS,
            ROLE_FINISHED_STARLESS,
            ROLE_FINISHED_COMPOSITE,
        ):
            self.assertIsNotNone(project.current_artifact_path(role))
        self.assertIsNone(project.current_export_path())

        project.record_export(export)
        project.update_settings(replace(project.get_settings(), blend_mode=BLEND_SCREEN))
        for role in (
            ROLE_SEPARATED_STARLESS,
            ROLE_DENOISE_ENDPOINT,
            ROLE_DENOISED_STARLESS,
            ROLE_FINISHED_STARLESS,
        ):
            self.assertIsNotNone(project.current_artifact_path(role))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())

        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        project.update_settings(replace(project.get_settings(), structure_amount=10.0))
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARLESS))
        self.assertIsNotNone(project.current_artifact_path(ROLE_DENOISE_ENDPOINT))
        self.assertIsNotNone(project.current_artifact_path(ROLE_DENOISED_STARLESS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARLESS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

        project.record_artifact(ROLE_FINISHED_STARLESS, finished_starless)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        project.update_settings(replace(project.get_settings(), denoise_strength=60.0))
        self.assertIsNotNone(project.current_artifact_path(ROLE_DENOISE_ENDPOINT))
        self.assertIsNone(project.current_artifact_path(ROLE_DENOISED_STARLESS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARLESS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())

    def test_toggling_starless_stages_preserves_stored_starless_layers(self):
        """Denoise and sharpen toggles are composite-only; stored plates survive."""
        project = FinishProject(project_file=str(self.root / f"starless_toggle{FINISH_EXT}"))
        source = self.create_synthetic_image("toggle_source.tif")
        project.set_source_image(source)
        starless = self.create_synthetic_image("toggle.finish/starless.tif", bit_depth=16)
        stars = self.create_synthetic_image("toggle.finish/stars.tif", bit_depth=16)
        endpoint = self.create_synthetic_image("toggle.finish/denoise_endpoint.tif", bit_depth=16)
        denoised = self.create_synthetic_image("toggle.finish/denoised.tif", bit_depth=16)
        finished_starless = self.create_synthetic_image("toggle.finish/finished_starless.tif", bit_depth=16)
        composite = self.create_synthetic_image("toggle.finish/composite.tif", bit_depth=16)
        export = self.create_synthetic_image("toggle.finish/export.tif", bit_depth=16)
        project.record_artifact(ROLE_SEPARATED_STARLESS, starless)
        project.record_artifact(ROLE_SEPARATED_STARS, stars)
        project.record_artifact(ROLE_DENOISE_ENDPOINT, endpoint)
        project.record_artifact(ROLE_DENOISED_STARLESS, denoised)
        project.record_artifact(ROLE_FINISHED_STARLESS, finished_starless)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        project.record_export(export)

        self.assertTrue(FINISH_DEFAULTS.enable_starless_denoise)
        self.assertTrue(FINISH_DEFAULTS.enable_starless_sharpen)
        for enable_denoise in (False, True):
            for enable_sharpen in (False, True):
                with self.subTest(enable_denoise=enable_denoise, enable_sharpen=enable_sharpen):
                    if project.current_artifact_path(ROLE_FINISHED_COMPOSITE) is None:
                        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
                    project.record_export(export)
                    self.assertIsNotNone(project.current_export_path())

                    project.update_settings(
                        replace(
                            project.get_settings(),
                            enable_starless_denoise=enable_denoise,
                            enable_starless_sharpen=enable_sharpen,
                        )
                    )

                    settings = project.get_settings()
                    self.assertEqual(settings.enable_starless_denoise, enable_denoise)
                    self.assertEqual(settings.enable_starless_sharpen, enable_sharpen)
                    self.assertEqual(project.current_artifact_path(ROLE_SEPARATED_STARLESS), starless)
                    self.assertEqual(project.current_artifact_path(ROLE_DENOISE_ENDPOINT), endpoint)
                    self.assertEqual(project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised)
                    self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished_starless)
                    self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
                    self.assertIsNone(project.current_export_path())
                    # All stored plates remain on disk for instant comparison.
                    for path in (starless, endpoint, denoised, finished_starless):
                        self.assertTrue(path.is_file(), path)

    def test_denoise_publication_persists_separate_outputs_and_invalidates_composite_export(self):
        project = FinishProject(project_file=str(self.root / f"denoise{FINISH_EXT}"))
        source = self.create_synthetic_image("denoise_source.tif")
        project.set_source_image(source)
        starless = self.create_synthetic_image("denoise.finish/starless.tif", bit_depth=16)
        stars = self.create_synthetic_image("denoise.finish/stars.tif", bit_depth=16)
        revision = project.processing_revision
        self.assertTrue(
            project.publish_separation(
                starless,
                stars,
                signature="separation-a",
                model_identity="nox-model",
                expected_revision=revision,
            )
        )
        composite = self.create_synthetic_image("denoise.finish/composite.tif", bit_depth=16)
        export = self.create_synthetic_image("denoise.finish/export.tif", bit_depth=16)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        project.record_export(export)
        self.assertIsNotNone(project.current_export_path())

        endpoint = self.create_synthetic_image("denoise.finish/denoise_endpoint.tif", bit_depth=16)
        denoised = self.create_synthetic_image("denoise.finish/denoised_starless.tif", bit_depth=16)
        finished = self.create_synthetic_image("denoise.finish/finished_starless.tif", bit_depth=16)
        revision = project.processing_revision
        self.assertTrue(
            project.publish_denoise_results(
                denoised,
                separation_signature="separation-a",
                expected_revision=revision,
                strength=50.0,
                scope="sky_only",
                structure_amount=35.0,
                detail_amount=15.0,
                starless_filter_version=STARLESS_FILTER_VERSION,
                finished_starless_path=finished,
                endpoint_path=endpoint,
                endpoint_signature="endpoint-key",
                model_identity="graxpert-model",
            )
        )
        self.assertEqual(project.denoise_signature, "endpoint-key")
        self.assertEqual(project.denoise_model_identity, "graxpert-model")
        self.assertEqual(project.current_artifact_path(ROLE_DENOISE_ENDPOINT), endpoint)
        self.assertEqual(project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised)
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished)

        endpoint_options = project.artifact_manifest[ROLE_DENOISE_ENDPOINT]["options"]
        self.assertEqual(endpoint_options["separation_signature"], "separation-a")
        self.assertEqual(endpoint_options["denoise_signature"], "endpoint-key")
        self.assertNotIn("structure_amount", endpoint_options)

        denoised_options = project.artifact_manifest[ROLE_DENOISED_STARLESS]["options"]
        self.assertEqual(denoised_options["denoise_strength"], 50.0)
        self.assertEqual(denoised_options["denoise_scope"], "sky_only")
        self.assertNotIn("structure_amount", denoised_options)
        self.assertNotIn("starless_filter_version", denoised_options)

        finished_options = project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]
        self.assertEqual(finished_options["denoise_strength"], 50.0)
        self.assertEqual(finished_options["denoise_scope"], "sky_only")
        self.assertEqual(finished_options["structure_amount"], 35.0)
        self.assertEqual(finished_options["detail_amount"], 15.0)
        self.assertEqual(finished_options["starless_filter_version"], STARLESS_FILTER_VERSION)
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())

        # Caller errors are rejected before staged files replace published plates.
        manifest = copy.deepcopy(project.artifact_manifest)
        published_bytes = {
            role: project.artifact_path(role).read_bytes()
            for role in (ROLE_DENOISE_ENDPOINT, ROLE_DENOISED_STARLESS, ROLE_FINISHED_STARLESS)
        }
        with ArtifactTransaction() as transaction:
            endpoint_dest = project.artifact_path(ROLE_DENOISE_ENDPOINT, for_write=True)
            Path(transaction.stage(endpoint_dest)).write_bytes(b"replacement endpoint")
            with self.assertRaisesRegex(ValueError, "signature and model identity"):
                project.publish_denoise_results(
                    separation_signature="separation-a",
                    expected_revision=project.processing_revision,
                    strength=50.0,
                    scope="sky_only",
                    structure_amount=35.0,
                    detail_amount=15.0,
                    starless_filter_version=STARLESS_FILTER_VERSION,
                    endpoint_path=endpoint_dest,
                    transaction=transaction,
                )
        with ArtifactTransaction() as transaction:
            denoised_dest = project.artifact_path(ROLE_DENOISED_STARLESS, for_write=True)
            Path(transaction.stage(denoised_dest)).write_bytes(b"replacement denoised")
            with self.assertRaisesRegex(ValueError, "paths must differ"):
                project.publish_denoise_results(
                    denoised_dest,
                    separation_signature="separation-a",
                    expected_revision=project.processing_revision,
                    strength=50.0,
                    scope="sky_only",
                    structure_amount=35.0,
                    detail_amount=15.0,
                    starless_filter_version=STARLESS_FILTER_VERSION,
                    finished_starless_path=denoised_dest,
                    transaction=transaction,
                )
        for role, content in published_bytes.items():
            self.assertEqual(project.artifact_path(role).read_bytes(), content)
        self.assertEqual(project.artifact_manifest, manifest)
        self.assertEqual(project.denoise_signature, "endpoint-key")

        # Publishing only the denoised plate preserves an already-current finished plate.
        finished_record = project.artifact_manifest[ROLE_FINISHED_STARLESS]
        self.assertTrue(
            project.publish_denoise_results(
                denoised,
                separation_signature="separation-a",
                expected_revision=project.processing_revision,
                strength=50.0,
                scope="sky_only",
                structure_amount=35.0,
                detail_amount=15.0,
                starless_filter_version=STARLESS_FILTER_VERSION,
                endpoint_signature="endpoint-key",
                model_identity="graxpert-model",
            )
        )
        self.assertEqual(project.artifact_manifest[ROLE_FINISHED_STARLESS], finished_record)
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished)

        # A stale job cannot replace the just-published plates.
        stale_revision = revision - 1
        self.assertFalse(
            project.publish_denoise_results(
                denoised,
                separation_signature="separation-a",
                expected_revision=stale_revision,
                strength=100.0,
                scope="whole_image",
                structure_amount=100.0,
                detail_amount=100.0,
                starless_filter_version=STARLESS_FILTER_VERSION,
                finished_starless_path=finished,
            )
        )

        project.invalidate_denoise_descendants()
        for role in (
            ROLE_DENOISE_ENDPOINT,
            ROLE_DENOISED_STARLESS,
            ROLE_FINISHED_STARLESS,
            ROLE_FINISHED_COMPOSITE,
        ):
            self.assertIsNone(project.current_artifact_path(role))
        self.assertIsNone(project.denoise_signature)
        self.assertIsNone(project.denoise_model_identity)

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
        for removed_role in ("star_catalog", "round_delta", "finished_stars"):
            with self.subTest(role=removed_role):
                with self.assertRaises(ValueError):
                    project.artifact_path(removed_role)

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
        self.assert_no_composite_export_rejected(app.workflow, new_dir / "shoot.finish/rejected.tif")
        self.register_composite_fixture(moved, bit_depth=16, value=23456)
        output = app.workflow.do_export_composite()
        decoded = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded.dtype, np.uint16)
        np.testing.assert_array_equal(decoded, 23456)

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

        self.assert_no_composite_export_rejected(workflow, self.root / "rejected.jpg")
        self.register_composite_fixture(project, bit_depth=8, value=17)

        exported_jpg = workflow.do_export_composite()
        self.assertTrue(exported_jpg.is_file())
        self.assertTrue(exported_jpg.name.endswith(".jpg"))
        decoded_jpg = cv2.imread(str(exported_jpg), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded_jpg.dtype, np.uint8)
        np.testing.assert_allclose(decoded_jpg, 17, atol=1)

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

        self.assert_no_composite_export_rejected(workflow, self.root / "rejected_tif8.tif")
        self.register_composite_fixture(project, bit_depth=8, value=34)

        exported_tif8 = workflow.do_export_composite()
        self.assertTrue(exported_tif8.is_file())
        decoded_tif8 = cv2.imread(str(exported_tif8), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded_tif8.dtype, np.uint8)
        np.testing.assert_array_equal(decoded_tif8, 34)

        with self.assertRaisesRegex(ValueError, "format must match"):
            workflow.do_export_composite(self.root / "wrong.jpg")

        # 3. 16-bit TIFF source -> exports 16-bit TIFF
        tif16_source = self.create_synthetic_image("night16.tif", bit_depth=16)
        workflow.do_replace_source(tif16_source)
        self.assertEqual(project.source_bit_depth, 16)
        self.assertTrue(project.get_default_export_path().name.endswith(".tif"))

        self.assert_no_composite_export_rejected(workflow, self.root / "rejected_tif16.tif")
        self.register_composite_fixture(project, bit_depth=16, value=12345)

        exported_tif16 = workflow.do_export_composite()
        self.assertTrue(exported_tif16.is_file())
        decoded_tif16 = cv2.imread(str(exported_tif16), cv2.IMREAD_UNCHANGED)
        self.assertEqual(decoded_tif16.dtype, np.uint16)
        np.testing.assert_array_equal(decoded_tif16, 12345)

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
        self.assertEqual(sidebar.inputFiles.model.files, [])
        self.assertEqual(sidebar.outputFiles.model.files, [])
        self.assertEqual(sidebar.skyCard._status, "locked")
        self.assertEqual(sidebar.separateCard._status, "locked")
        self.assertEqual(sidebar.starlessCard._status, "locked")
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

        inputs = sidebar.inputFiles.model.files
        self.assertEqual(len(inputs), 1)
        self.assertEqual(Path(inputs[0].path), Path(img_path).resolve())
        self.assertEqual(sidebar.outputFiles.model.files, [])
        self.assertNotIn("source_dimensions", project.__getstate__())
        self.assertNotIn("source_format", project.__getstate__())

        # Step 1 is ready, Step 2 remains locked until mask is defined
        self.assertEqual(sidebar.skyCard._status, "ready")
        self.assertEqual(sidebar.separateCard._status, "locked")

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
        self.assertEqual(sidebar.recombineCard._status, "ready")
        self.assertEqual({f.operation for f in sidebar.outputFiles.model.files}, {"Starless", "Stars"})
        # Save explicitly recombines current layers when no composite is cached.
        self.assertTrue(sidebar.btn_save_output.isEnabled())

        composite_path = project.artifact_path(ROLE_FINISHED_COMPOSITE)
        imwrite(composite_path, np.zeros((80, 100, 3), dtype=np.uint16), bit_depth=16)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite_path)
        view.updateReadyStates()
        self.assertEqual(
            {f.operation for f in sidebar.outputFiles.model.files},
            {"Starless", "Stars", "Composite"},
        )
        self.assertTrue(sidebar.btn_save_output.isEnabled())

        # Output files list in sidebar shows published artifacts
        outputs = app.workflow.get_output_file_list()
        self.assertGreaterEqual(len(outputs), 2)
        sidebar.outputFiles.set_files(outputs)
        self.assertEqual(len(sidebar.outputFiles.model.files), len(outputs))

        self.create_synthetic_image("imported.jpg", shape=(40, 60, 3))
        app.workflow.do_replace_source(img_path)
        view.resetProjectView()
        self.assertEqual(shell.canvas_main.pixmap.width(), 60)
        inputs = sidebar.inputFiles.model.files
        self.assertEqual(len(inputs), 1)
        self.assertEqual(Path(inputs[0].path), Path(img_path).resolve())
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

        default_export = project.get_default_export_path()
        with self.assertRaisesRegex(ValueError, "No current composite"):
            app.workflow.do_export_composite()
        self.assertFalse(default_export.exists())

        composite = project.artifact_path(ROLE_FINISHED_COMPOSITE)
        composite.parent.mkdir(parents=True, exist_ok=True)
        imwrite(composite, np.full((16, 16, 3), 34, dtype=np.uint8), bit_depth=8)
        # Existing files are not published just because they use a default filename.
        self.assertEqual(app.workflow.get_output_file_list(), [])
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        self.assertEqual(len(app.workflow.get_output_file_list()), 1)
        app.workflow.save_project()
        app.loadProject(project.project_file)
        project = app.project
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), composite)
        result = app.workflow.do_export_composite()
        np.testing.assert_array_equal(cv2.imread(str(result), cv2.IMREAD_UNCHANGED), 34)
        prior_export = Path(result)
        prior_bytes = prior_export.read_bytes()

        stamp = composite.stat()
        os.utime(composite, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)
        replacement = self.create_synthetic_image("second.tif")
        app.workflow.do_replace_source(replacement)
        self.assertTrue(composite.is_file())
        self.assertIsNone(project.composite_path)
        self.assertEqual(app.workflow.get_output_file_list(), [])

        # A missing composite must never fall back to exporting the source.
        with self.assertRaisesRegex(ValueError, "No current composite"):
            app.workflow.do_export_composite()
        self.assertTrue(prior_export.is_file())
        self.assertEqual(prior_export.read_bytes(), prior_bytes)

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

    def test_project_buttons_open_overlay_in_all_modes(self):
        from startrails.lib.project_type import DENOISE_EXT, STARTRAILS_EXT
        from startrails.ui.ui_wrap import MainWindow

        app = self.make_app()
        window = MainWindow(app)
        self.addCleanup(window.close)

        projects = (
            ("startrails", self.root / f"st{STARTRAILS_EXT}"),
            ("denoise", self.root / f"dn{DENOISE_EXT}"),
            ("finish", self.root / f"fn{FINISH_EXT}"),
        )
        for mode, project_path in projects:
            with self.subTest(mode=mode):
                app.newProject(str(project_path))
                window.ui.switch_to_project_mode()
                self.assertEqual(window.ui.active_view.mode_name, mode)
                window.hide_project_overlay()

                window.ui.pushButton_newProject.click()
                self.assertTrue(window.project_overlay.isVisible())
                self.assertEqual(window.project_overlay._mode, "new")

                window.hide_project_overlay()
                window.ui.pushButton_openProject.click()
                self.assertTrue(window.project_overlay.isVisible())
                self.assertEqual(window.project_overlay._mode, "open")
