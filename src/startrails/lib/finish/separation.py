"""Working-region star separation and processing signatures.

Persist ordinary unsigned images. Signed residuals are derived from the source
and the original separated starless image, never from a subsequently finished
starless plate. Callers decode both into normalized float32 before subtraction.
"""

import numpy as np

from startrails.lib.image_io import validate_image_array
from startrails.lib.signatures import compute_signature


def separate_stars(source: np.ndarray, model_starless: np.ndarray, sky_mask: np.ndarray) -> np.ndarray:
    """Return the masked starless working region B=M*B_model+(1-M)*I.

    Inputs are normalized float32 RGB and mask arrays. Call with row chunks to
    bound temporary allocations. No image files or result caches are owned here.
    """
    if source.shape != model_starless.shape:
        raise ValueError("Source and starless image shapes must match.")
    validate_image_array(source)
    validate_image_array(model_starless)
    if sky_mask.dtype != np.float32 or sky_mask.shape != source.shape[:2]:
        raise ValueError("Sky mask must be normalized float32 with source dimensions.")
    if not np.isfinite(sky_mask).all() or np.any(sky_mask < 0) or np.any(sky_mask > 1):
        raise ValueError("Sky mask values must be finite and in [0,1].")
    weight = sky_mask[..., None]
    return weight * model_starless + (1 - weight) * source


def star_residual(source: np.ndarray, separated_starless: np.ndarray) -> np.ndarray:
    """Derive signed I-B for a working region; never subtract unsigned samples.

    Derive positive stars as max(I-B,0), and additive corrections as min(I-B,0).
    Re-derive against the decoded persisted B on reopen to include its rounding.
    """
    if source.shape != separated_starless.shape:
        raise ValueError("Source and separated starless image shapes must match.")
    if source.dtype != np.float32 or separated_starless.dtype != np.float32:
        raise ValueError("Residual arithmetic requires normalized float32 images.")
    return source - separated_starless


def compute_separation_signature(
    source_id: str,
    mask_id: str,
    model_identity: str,
    *,
    stride: int,
    upsample: bool,
    linear: bool,
    highlights_protection: bool,
    mask_feather_radius_px: float,
) -> str:
    """Hash source, effective-mask and CLI/package identities.

    Caller resolves all options. model_identity includes the verified package,
    model hash and selected platform backend. Bump schema when arithmetic changes.
    """
    return compute_signature(
        {
            "operation": "finish_separation",
            "version": 2,
            "source": source_id,
            "mask": mask_id,
            "model": model_identity,
            "stride": stride,
            "upsample": upsample,
            "linear": linear,
            "highlights_protection": highlights_protection,
            "mask_feather_radius_px": mask_feather_radius_px,
        }
    )
