"""Sky-masked star separation published as ordinary image outputs."""

from concurrent.futures import CancelledError
from pathlib import Path

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.file import OutputFile
from startrails.lib.finish.defaults import FinishSettings, INTERMEDIATE_BIT_DEPTH
from startrails.lib.finish.separation import separate_stars, star_residual
from startrails.lib.image_io import imwrite, normalize_image, quantize_image
from startrails.lib.util import Observable


class SeparateStars(Observable):
    """Write lossless 16-bit TIFF intermediates, returning existing file records.

    One uint16 output buffer is reused for both images; working float allocations
    are bounded by chunk_rows. Keep the original source for signed corrections on
    recombination/reopen. User exports receive source bit depth and a source-matching output path.
    """

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    def separate(
        self,
        source: np.ndarray,
        model_starless: np.ndarray,
        sky_mask: np.ndarray,
        *,
        starless_path: Path,
        stars_path: Path,
        chunk_rows: int,
        settings: FinishSettings,
    ) -> tuple[OutputFile, OutputFile] | None:
        """Publish (starless, positive stars) lossless TIFF intermediates.

        Source/model inputs and mask are already normalized float32. Stars are
        computed against the quantized starless plate that is actually saved.
        Cancellation/failure keeps both previously published images intact.
        """
        starless_path, stars_path = Path(starless_path).resolve(), Path(stars_path).resolve()
        if starless_path == stars_path:
            raise ValueError("Starless and stars output paths must differ.")
        if any(path.suffix.lower() not in (".tif", ".tiff") for path in (starless_path, stars_path)):
            raise ValueError("Separation intermediates must be lossless TIFF images.")
        if chunk_rows <= 0:
            raise ValueError("chunk_rows must be positive.")
        if source.ndim != 3 or source.shape[2] != 3 or any(size <= 0 for size in source.shape):
            raise ValueError("Source must have positive (height, width, 3) dimensions.")
        if source.shape != model_starless.shape or sky_mask.shape != source.shape[:2]:
            raise ValueError("Source, model and sky mask dimensions must match.")
        height = source.shape[0]
        chunks = (height + chunk_rows - 1) // chunk_rows
        self.startJob(2 * chunks + 2)
        if self.shouldInterrupt():
            return None

        pixels = np.empty(source.shape, dtype=np.uint16)
        try:
            with ArtifactTransaction(self.shouldInterrupt) as transaction:
                for start in range(0, height, chunk_rows):
                    if self.shouldInterrupt():
                        return None
                    end = min(start + chunk_rows, height)
                    base = separate_stars(source[start:end], model_starless[start:end], sky_mask[start:end])
                    pixels[start:end] = quantize_image(base, bit_depth=INTERMEDIATE_BIT_DEPTH)
                    self.updateJob(1, {"desc": "Calculating starless image..."})
                if self.shouldInterrupt():
                    return None
                imwrite(
                    transaction.stage(starless_path),
                    pixels,
                    convertBGR=True,
                    bit_depth=INTERMEDIATE_BIT_DEPTH,
                    compression=False,
                )
                self.updateJob(1, {"desc": "Starless image staged."})
                # The saved plate is complete. Reuse its integer buffer rather
                # than retaining a second full-frame stars/residual array.
                for start in range(0, height, chunk_rows):
                    if self.shouldInterrupt():
                        return None
                    end = min(start + chunk_rows, height)
                    residual = star_residual(source[start:end], normalize_image(pixels[start:end]))
                    np.maximum(residual, 0, out=residual)
                    pixels[start:end] = quantize_image(residual, bit_depth=INTERMEDIATE_BIT_DEPTH)
                    self.updateJob(1, {"desc": "Calculating stars image..."})
                if self.shouldInterrupt():
                    return None
                imwrite(
                    transaction.stage(stars_path),
                    pixels,
                    convertBGR=True,
                    bit_depth=INTERMEDIATE_BIT_DEPTH,
                    compression=False,
                )
                if self.shouldInterrupt():
                    return None
                transaction.commit()
        except CancelledError:
            return None
        self.updateJob(1, {"desc": "Separation complete."})
        return (
            OutputFile(basename=starless_path.name, path=str(starless_path), operation="Starless"),
            OutputFile(basename=stars_path.name, path=str(stars_path), operation="Stars"),
        )
