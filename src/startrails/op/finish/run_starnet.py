"""Observable operation for launching and monitoring the StarNet CLI subprocess."""

from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from startrails.lib.finish.starnet import (
    build_starnet_cli_args,
    run_starnet_process,
    StarNetError,
)
from startrails.lib.util import Observable
from startrails.lib.artifacts import ArtifactTransaction


class RunStarNet(Observable):
    """Observable operation running StarNet CLI with progress monitoring and cancellation."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self._last_percent: int = 0

    def run(
        self,
        executable_path: Union[str, Path],
        input_image_path: Union[str, Path],
        output_starless_path: Union[str, Path],
        *,
        output_stars_path: Optional[Union[str, Path]] = None,
        stride: int,
        disable_highlights: bool,
        upsample: bool,
    ) -> Optional[Tuple[Path, Optional[Path]]]:
        """Launch StarNet CLI subprocess and report incremental progress."""
        exec_p = Path(executable_path).resolve()
        input_p = Path(input_image_path).resolve()
        starless_p = Path(output_starless_path).resolve()
        stars_p = Path(output_stars_path).resolve() if output_stars_path is not None else None

        if not exec_p.is_file():
            raise FileNotFoundError(f"StarNet executable not found: {exec_p}")
        if not input_p.is_file():
            raise FileNotFoundError(f"Input image not found: {input_p}")

        destinations = [starless_p] + ([stars_p] if stars_p is not None else [])
        if input_p in destinations or len(set(destinations)) != len(destinations):
            raise ValueError("StarNet output paths must be distinct from each other and the input.")
        starless_p.parent.mkdir(parents=True, exist_ok=True)
        if stars_p is not None:
            stars_p.parent.mkdir(parents=True, exist_ok=True)

        self.startJob(100)
        self._last_percent = 0
        if self.shouldInterrupt():
            return None

        def on_progress(event: Dict[str, Any]) -> None:
            if not isinstance(event, dict):
                return
            percent = event.get("percent")
            if isinstance(percent, (int, float)):
                target_p = min(100, max(0, int(percent)))
                delta = target_p - self._last_percent
                if delta > 0:
                    self._last_percent = target_p
                    desc = f"Separating stars: {target_p}%"
                    self.updateJob(delta, {"desc": desc})

        try:
            with ArtifactTransaction(self.shouldInterrupt, prefix=".starnet-") as transaction:
                staged_starless = transaction.stage(starless_p)
                staged_stars = transaction.stage(stars_p) if stars_p is not None else None
                cmd = build_starnet_cli_args(
                    str(exec_p),
                    str(input_p),
                    str(staged_starless),
                    mask_path=str(staged_stars) if staged_stars is not None else None,
                    stride=stride,
                    disable_highlights=disable_highlights,
                    upsample=upsample,
                    machine_progress=True,
                )
                # StarNet resolves its shipped libraries/assets relative to the helper.
                run_starnet_process(
                    cmd, cwd=str(exec_p.parent), progress_callback=on_progress, should_interrupt=self.shouldInterrupt
                )
                for output in (staged_starless, staged_stars):
                    if output is not None and (not output.is_file() or output.stat().st_size == 0):
                        raise StarNetError("StarNet completed without creating the requested output.")
                transaction.commit()
        except CancelledError:
            return None

        # Ensure progress completes to 100%
        if self._last_percent < 100:
            self.updateJob(100 - self._last_percent, {"desc": "StarNet processing complete."})

        return starless_p, stars_p


__all__ = ["RunStarNet"]
