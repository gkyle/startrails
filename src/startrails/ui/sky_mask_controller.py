"""Shared sky mask controller managing canvas interactions and workflow callbacks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple
import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, QSignalBlocker

from startrails.lib.denoise.defaults import DEFAULT_SKY_DETECTION_INPUT_SIZE
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.sky_mask_settings import SkyMaskSettings

if TYPE_CHECKING:
    from startrails.ui.steps import StepCard


_MASK_STAGE_PROGRESS_UNITS = 500


class SkyMaskController(QObject):
    """Coordinates sky mask interactions between the UI canvas, settings widget, and workflow.

    Uses explicit per-workflow callbacks so that neither Finish nor Denoise couples
    to the other's project model, invalidation lifecycle, or storage conventions.
    """

    def __init__(
        self,
        shell: Any,
        settings_widget: SkyMaskSettings,
        *,
        get_source_image: Callable[[], Optional[Any]],
        show_source_image: Callable[[], None],
        get_saved_mask: Callable[[], Optional[np.ndarray]],
        save_mask: Callable[[np.ndarray], None],
        detect_sky_fn: Callable[..., Optional[np.ndarray]],
        refine_mask_fn: Callable[..., Optional[np.ndarray]],
        enqueue_task: Callable[[str, str, int, str, Callable], bool],
        get_post_result: Callable[[], Callable[[Callable], None]],
        get_result_guard: Callable[[], Callable[[], bool]],
        on_manual_edit: Optional[Callable[[], None]] = None,
        on_detection_finished: Optional[Callable[[np.ndarray], None]] = None,
        sky_card: Optional[StepCard] = None,
        get_device: Callable[[], str],
    ):
        super().__init__()
        self.shell = shell
        self.settings_widget = settings_widget
        self.get_source_image = get_source_image
        self.show_source_image = show_source_image
        self.get_saved_mask = get_saved_mask
        self.save_mask = save_mask
        self.detect_sky_fn = detect_sky_fn
        self.refine_mask_fn = refine_mask_fn
        self.enqueue_task = enqueue_task
        self.get_post_result = get_post_result
        self.get_result_guard = get_result_guard
        self.on_manual_edit = on_manual_edit
        self.on_detection_finished = on_detection_finished
        self.sky_card = sky_card
        self.get_device = get_device

        self._signal_connections: List[Tuple[Any, Callable]] = []

    def bind(self) -> None:
        """Connect UI signals, settings widget triggers, and canvas event listeners."""
        ui = self.settings_widget.ui
        self._connect(ui.detect.clicked, self.do_detect_sky)
        self._connect(ui.refineMask.clicked, self.do_refine_mask)
        self._connect(self.settings_widget.clear_mask_requested, self.do_clear_mask)
        self._connect(self.settings_widget.full_frame_requested, self.do_full_frame_mask)
        self._connect(self.settings_widget.mask_edit_toggled, self.on_mask_edit_toggled)
        self._connect(self.settings_widget.brush_radius_changed, self.on_brush_radius_changed)

        if self.sky_card is not None:
            self._connect(self.sky_card.expansion_changed, self.settings_widget.ui.showMaskOverlay.setChecked)

        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            self._connect(canvas.mask_changed, self.on_canvas_mask_changed)
            self._connect(canvas.mask_brush_edited, self.on_canvas_mask_brush_edited)
            self._connect(canvas.brush_radius_changed, self.on_canvas_brush_radius_changed)

    def teardown(self) -> None:
        """Clean up canvas state and disconnect all tracked signals."""
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_mask_edit_mode(False)
            canvas.set_denoise_mask(None)

        for sig, slot in self._signal_connections:
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._signal_connections.clear()

    def _connect(self, signal: Any, slot: Callable) -> None:
        signal.connect(slot)
        self._signal_connections.append((signal, slot))

    def apply_mask_to_canvas(self, mask: np.ndarray) -> None:
        """Render mask overlay on top of the active source image."""
        self.show_source_image()
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_denoise_mask(mask)
            canvas.set_mask_edit_mode(True)
        with QSignalBlocker(self.settings_widget.ui.showMaskOverlay):
            self.settings_widget.ui.showMaskOverlay.setChecked(True)

    def _on_detection_completed(self, mask: np.ndarray) -> None:
        if self.on_detection_finished is not None:
            self.on_detection_finished(mask)
        self.save_mask(mask)
        self.apply_mask_to_canvas(mask)
        if self.sky_card is not None:
            self.sky_card.setStatus("done", "Sky mask defined")

    def do_detect_sky(self) -> None:
        """Execute autonomous neural sky detection and horizon refinement."""
        src = self.get_source_image()
        if src is None:
            return

        self.show_source_image()

        vals = self.settings_widget.values()
        search_radius = vals["mask_search_radius"]
        erosion_pixels = vals["mask_erosion_pixels"]
        foliage_protection = vals["mask_foliage_protection"]
        model_type = vals["auto_mask_model"]
        model_path = vals["auto_mask_path"]
        device = self.get_device()
        src_path = getattr(src, "path", src)

        result_guard = self.get_result_guard()
        deliver_result = self.get_post_result()

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2 * _MASK_STAGE_PROGRESS_UNITS,
                desc="Detecting sky mask...",
                result_guard=result_guard,
            )
            reported = 0

            def report_stage(offset, total, count, done, data):
                nonlocal reported
                target = offset + (
                    _MASK_STAGE_PROGRESS_UNITS if done else round(_MASK_STAGE_PROGRESS_UNITS * count / max(total, 1))
                )
                increment = max(0, target - reported)
                reported += increment
                progress_updater.tick(
                    2 * _MASK_STAGE_PROGRESS_UNITS,
                    increment,
                    reported,
                    offset == _MASK_STAGE_PROGRESS_UNITS and done,
                    data,
                )

            def on_detect_tick(total, inc, count, done, data=None):
                report_stage(0, total, count, done, data)

            coarse_mask = self.detect_sky_fn(
                src_path,
                progress_bar=on_detect_tick,
                model_type=model_type,
                model_path=model_path,
                device=device,
                input_size=DEFAULT_SKY_DETECTION_INPUT_SIZE,
            )
            if coarse_mask is None:
                return

            progress_updater.tick(
                2 * _MASK_STAGE_PROGRESS_UNITS, 0, reported, False, {"desc": "Refining detected sky mask..."}
            )

            def on_refine_tick(total, inc, count, done, data=None):
                report_stage(_MASK_STAGE_PROGRESS_UNITS, total, count, done, data)

            refined_mask = self.refine_mask_fn(
                src_path,
                coarse_mask,
                progress_bar=on_refine_tick,
                search_radius=search_radius,
                erosion_pixels=erosion_pixels,
                foliage_protection=foliage_protection,
            )
            if refined_mask is None:
                return

            deliver_result(lambda m=refined_mask: self._on_detection_completed(m))

        self.enqueue_task("detectSky", "Detect Sky", 1, "Detecting and refining sky mask...", work)

    def do_refine_mask(self) -> None:
        """Refine rough sky boundaries using current search radius and erosion settings."""
        src = self.get_source_image()
        if src is None:
            return

        self.show_source_image()
        canvas = getattr(self.shell, "canvas_main", None)
        current_mask = canvas.get_denoise_mask() if canvas is not None else None
        if current_mask is None or not np.any(current_mask > 0):
            current_mask = self.get_saved_mask()
        if current_mask is None or not np.any(current_mask > 0):
            return

        current_mask = current_mask.copy()
        if canvas is not None and self.settings_widget.ui.showMaskOverlay.isChecked():
            canvas.set_mask_edit_mode(True)

        vals = self.settings_widget.values()
        search_radius = vals["mask_search_radius"]
        erosion_pixels = vals["mask_erosion_pixels"]
        foliage_protection = vals["mask_foliage_protection"]
        src_path = getattr(src, "path", src)

        result_guard = self.get_result_guard()
        deliver_result = self.get_post_result()

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Refining sky mask...",
                result_guard=result_guard,
            )
            refined = self.refine_mask_fn(
                src_path,
                current_mask,
                progress_bar=progress_updater.tick,
                search_radius=search_radius,
                erosion_pixels=erosion_pixels,
                foliage_protection=foliage_protection,
            )
            if refined is not None:
                deliver_result(lambda r=refined: self._on_detection_completed(r))

        self.enqueue_task("refineMask", "Refine Mask", 1, "Refining sky mask...", work)

    def _fill_mask(self, value: float) -> None:
        src = self.get_source_image()
        if src is None:
            return
        self.show_source_image()
        src_path = getattr(src, "path", src)
        with Image.open(src_path) as image:
            width, height = image.size
        mask = np.full((height, width), value, dtype=np.float32)
        self.save_mask(mask)
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_denoise_mask(mask)

    def do_clear_mask(self) -> None:
        """Publish an all-ground mask, including when there is no previous mask."""
        self._fill_mask(0.0)

    def do_full_frame_mask(self) -> None:
        """Publish an all-sky mask at the source image's dimensions."""
        self._fill_mask(1.0)

    def on_mask_edit_toggled(self, enabled: bool) -> None:
        """Toggle canvas mask overlay and interactive brush editing mode."""
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is None:
            return
        if enabled:
            src = self.get_source_image()
            if src is None:
                canvas.set_mask_edit_mode(False)
                return
            self.show_source_image()

            current_m = canvas.get_denoise_mask()
            if current_m is None:
                existing_mask = self.get_saved_mask()
                if existing_mask is not None:
                    canvas.set_denoise_mask(existing_mask)
                else:
                    canvas.fill_denoise_mask()
        canvas.set_mask_edit_mode(enabled)

    def on_brush_radius_changed(self, radius: int) -> None:
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_brush_radius(radius)

    def on_canvas_brush_radius_changed(self, radius: int) -> None:
        with QSignalBlocker(self.settings_widget.ui.brushSlider):
            self.settings_widget.ui.brushSlider.setValue(radius)
        with QSignalBlocker(self.settings_widget.ui.brushRadius):
            self.settings_widget.ui.brushRadius.setValue(radius)

    def on_canvas_mask_brush_edited(self) -> None:
        if self.on_manual_edit is not None:
            self.on_manual_edit()

    def on_canvas_mask_changed(self) -> None:
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is None:
            return
        mask = canvas.get_denoise_mask()
        if mask is not None:
            self.save_mask(mask)


__all__ = ["SkyMaskController"]
