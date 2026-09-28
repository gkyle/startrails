"""Persistent, per-channel provenance for a particular completed stack."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np


class SourceMapError(ValueError):
    """An unavailable map or source, with an explanation suitable for the UI."""


@dataclass
class SourceLookup:
    candidates: list = field(default_factory=list)
    message: str = ""


def source_dtype(count):
    # Reserve the largest value for black/masked pixels with no contribution.
    return np.uint16 if count <= np.iinfo(np.uint16).max else np.uint32


def signature(path):
    stat = Path(path).stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def relative_path(path, directory):
    try:
        return os.path.relpath(Path(path).resolve(), Path(directory).resolve())
    except ValueError:  # Different Windows drives.
        return str(Path(path).resolve())


def output_sidecar(output, name):
    value = getattr(output, name, None)
    return Path(output.path).resolve().parent / value if value else None


@contextmanager
def atomic_file(path, mode):
    """Publish complete sidecars; incomplete writes are never opened by lookup."""
    path = Path(path)
    handle = tempfile.NamedTemporaryFile(mode=mode, dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_source_map(output, owners, sources, settings):
    """Write the array first, then its manifest; attach only after both succeed."""
    image_path = Path(output.path).resolve()
    array_path = image_path.with_name(image_path.name + ".sources.npy")
    manifest_path = image_path.with_name(image_path.name + ".sources.json")
    manifest = {
        "version": 1,
        "array": array_path.name,
        "shape": list(owners.shape),
        "dtype": owners.dtype.name,
        "no_source": int(np.iinfo(owners.dtype).max),
        "stack": image_path.name,
        "stack_signature": signature(image_path),
        "settings": settings,
        "sources": sources,
    }
    with atomic_file(array_path, "wb") as stream:
        np.save(stream, owners, allow_pickle=False)
    try:
        with atomic_file(manifest_path, "w") as stream:
            json.dump(manifest, stream, indent=2)
    except Exception:
        array_path.unlink(missing_ok=True)
        raise
    output.sourceMap = manifest_path.name


def snapshot_sources(files, output):
    directory = Path(output.path).resolve().parent
    return [{"id": file.sourceId, "path": relative_path(file.path, directory),
             "basename": file.basename, "signature": signature(file.path)} for file in files]


def locate_sources(output, files, x, y, radius=6, limit=8):
    """Read a small map region and one stack image, without decoding input images."""
    manifest_path = output_sidecar(output, "sourceMap")
    if manifest_path is None:
        raise SourceMapError("This output has no source map. Build a new stack to use Locate Source.")
    owners = None
    try:
        with manifest_path.open(encoding="utf-8") as stream:
            manifest = json.load(stream)
        if manifest["version"] != 1:
            raise SourceMapError("This source map uses an unsupported version. Build a new stack.")
        stack_path = manifest_path.parent / manifest["stack"]
        if signature(stack_path) != manifest["stack_signature"]:
            raise SourceMapError("The stacked image has changed since its source map was saved. Build a new stack.")
        owners = np.load(manifest_path.parent / manifest["array"], mmap_mode="r", allow_pickle=False)
        if (list(owners.shape) != manifest["shape"] or owners.dtype.name != manifest["dtype"]
                or owners.dtype not in (np.dtype('uint16'), np.dtype('uint32'))
                or owners.ndim not in (2, 3)):
            raise SourceMapError("The source map does not match this stack. Build a new stack.")
        height, width = owners.shape[:2]
        if not (0 <= x < width and 0 <= y < height):
            return SourceLookup(message="Click inside the stacked image.")
        x, y = int(x), int(y)
        y0, y1 = max(0, y - radius), min(height, y + radius + 1)
        x0, x1 = max(0, x - radius), min(width, x + radius + 1)
        region = np.array(owners[y0:y1, x0:x1], copy=True)
        stack = cv2.imread(str(stack_path), cv2.IMREAD_UNCHANGED)
        if stack is None or stack.shape != owners.shape:
            raise SourceMapError("The original stacked image could not be read. Restore it or build a new stack.")
        values = stack[y0:y1, x0:x1].astype(np.float32)
        del stack
        if region.ndim == 2:
            region, values = region[..., None], values[..., None]
        valid = region != manifest["no_source"]
        synthesized = False
        if output.operation == "FillGaps":
            mask_path = output_sidecar(output, "gapMask")
            mask = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED) if mask_path else None
            if mask is None or mask.shape[:2] != (height, width):
                raise SourceMapError("The gap-fill mask is unavailable. Use Locate Source on the original stack.")
            synthesized = bool(np.any(mask[y, x]))
            patch = mask[y0:y1, x0:x1]
            if patch.ndim == 3:
                patch = np.any(patch != 0, axis=2)
            valid &= (patch == 0)[..., None]
        if np.any(valid & (region >= len(manifest["sources"]))):
            raise SourceMapError("The source map contains invalid source IDs. Build a new stack.")
        # Exact clicked contributors come first; nearby contrast helps thin streaks
        # compete with large areas of uninteresting background.
        yy, xx = np.mgrid[y0:y1, x0:x1]
        spatial = 1.0 / (1.0 + (xx - x)**2 + (yy - y)**2)
        contrast = np.maximum(values - np.median(values, axis=(0, 1)), 0)
        weights = (contrast + values * 0.01 + 1) * spatial[..., None]
        cy, cx = y - y0, x - x0
        exact_ids = set(region[cy, cx][valid[cy, cx]].tolist())
        ids, inverse = np.unique(region[valid], return_inverse=True)
        scores = np.bincount(inverse, weights=weights[valid])
        ranked = sorted(zip(ids.tolist(), scores.tolist()),
                        key=lambda pair: (pair[0] not in exact_ids, -pair[1], pair[0]))
        by_id = {file.sourceId: file for file in files}
        by_path = {os.path.normcase(str(Path(file.path).resolve())): file for file in files}
        candidates = []
        unavailable = 0
        for source_id, _ in ranked:
            source = manifest["sources"][source_id]
            source_path = (manifest_path.parent / source["path"]).resolve()
            file = by_id.get(source["id"]) or by_path.get(os.path.normcase(str(source_path)))
            try:
                available = file is not None and signature(file.path) == source["signature"]
            except OSError:
                available = False
            if not available:
                unavailable += 1
                continue
            if file not in candidates:
                candidates.append(file)
            if len(candidates) >= limit:
                break
        message = ""
        if synthesized:
            message = "This pixel was generated by gap filling. Showing nearby original contributors."
        if unavailable:
            message += " Some source images are missing, changed, or no longer in this project."
        if not candidates:
            message += " No available source contributed in this area."
        return SourceLookup(candidates, message.strip())
    except SourceMapError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, EOFError) as error:
        raise SourceMapError("The source map could not be read. Restore its sidecar files or build a new stack.") from error
    finally:
        if owners is not None and getattr(owners, "_mmap", None) is not None:
            owners._mmap.close()
