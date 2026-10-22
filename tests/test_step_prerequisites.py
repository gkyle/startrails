"""Step actions follow input, mask, and compositor prerequisites."""

from support import QtTestCase, qt_app

QT_APP = qt_app()


class StepPrerequisiteTests(QtTestCase):
    def test_denoise_steps_follow_prerequisites_and_preserve_auto_alignment(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from startrails.lib.project_denoise import DenoiseProject
        from startrails.lib.file import DenoiseInputFile
        from startrails.ui.sidebar_denoise import SidebarDenoise

        with tempfile.TemporaryDirectory() as folder:
            project = DenoiseProject(str(Path(folder) / "project.proj_denoise"))
            workflow = SimpleNamespace(project=project, get_star_files=lambda: project.star_files)
            app = SimpleNamespace(project=project, workflow=workflow)
            sidebar = SidebarDenoise(app=app)
            try:
                for card in (c for c in sidebar._step_cards if c.has_number):
                    card.setExpanded(True)
                    self.assertFalse(card.is_expanded)
                project.star_files = [DenoiseInputFile("star.tif", str(Path(folder) / "star.tif"))]
                sidebar.update_operations_progress()
                self.assertFalse(sidebar.alignSettings.ui.run.isEnabled())
                self.assertFalse(sidebar.stackSettings.ui.run.isEnabled())
                mask_path = Path(folder) / "mask.png"
                mask_path.write_bytes(b"saved mask")
                project.mask_path = str(mask_path)
                sidebar.update_operations_progress()
                self.assertTrue(sidebar.alignSettings.ui.run.isEnabled())
                self.assertTrue(sidebar.stackSettings.ui.run.isEnabled())
                sidebar.set_has_compositor(True)
                sidebar.update_operations_progress()
                sidebar.set_output_saved(True)
                sidebar.update_operations_progress()
                sidebar.stackCard.setExpanded(True)
                mask_path.unlink()
                sidebar.set_has_compositor(False)
                sidebar.update_operations_progress()
                self.assertFalse(sidebar.stackCard.is_expanded)
                self.assertFalse(sidebar.stackSettings.ui.run.isEnabled())
                mask_path.write_bytes(b"saved mask")
                project.mask_invalidated = True
                sidebar.update_operations_progress()
            finally:
                sidebar.deleteLater()
                QT_APP.processEvents()
