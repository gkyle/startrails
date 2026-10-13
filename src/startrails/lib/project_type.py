"""Project type detection, extension constants, and output directory resolution."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Union
import jsonpickle

STARTRAILS_EXT = ".proj_startrails"
DENOISE_EXT = ".proj_denoise"
LEGACY_STARTRAILS_EXT = ".project.json"

TYPE_STARTRAILS = "startrails"
TYPE_DENOISE = "denoise"


class UnsupportedProjectError(ValueError):
    """Raised when an unsupported project format (such as XML) is encountered."""
    pass


class InvalidProjectError(ValueError):
    """Raised when a project file cannot be parsed or decoded as a valid project."""
    pass


def get_project_output_dir(project_file: Union[str, Path]) -> Path:
    """Resolve the authoritative output directory for a project file.

    Preserves legacy output directories (e.g. '<name>.project' for '<name>.project.json'
    or when '<name>.project' exists beside '<name>.proj_startrails' / '<name>.proj_denoise').
    Otherwise resolves to '<name>' directory in the project's parent directory.
    """
    path = Path(project_file).resolve()
    parent = path.parent
    name = path.name

    if name.endswith(LEGACY_STARTRAILS_EXT):
        # Strips ".json", yielding '<name>.project'
        return parent / name[:-5]

    if name.endswith(STARTRAILS_EXT):
        base = name[:-len(STARTRAILS_EXT)]
        # If legacy '<base>.project' directory exists, preserve it
        legacy_dir = parent / f"{base}.project"
        if legacy_dir.is_dir():
            return legacy_dir
        return parent / base

    if name.endswith(DENOISE_EXT):
        base = name[:-len(DENOISE_EXT)]
        legacy_dir = parent / f"{base}.project"
        if legacy_dir.is_dir():
            return legacy_dir
        return parent / base

    if name.endswith(".json"):
        return parent / name[:-5]

    return parent / path.stem


def detect_project_type_from_path(path: Union[str, Path]) -> str:
    """Detect project type purely by file extension without reading content."""
    name = str(path).lower()
    if name.endswith(DENOISE_EXT):
        return TYPE_DENOISE
    if name.endswith(STARTRAILS_EXT) or name.endswith(LEGACY_STARTRAILS_EXT):
        return TYPE_STARTRAILS
    if name.endswith(".xml"):
        raise UnsupportedProjectError(f"Unsupported XML project format: {path}")
    return TYPE_STARTRAILS


def detect_project_type(target: Union[str, Path, Any]) -> str:
    """Detect whether target is a StarTrails or Denoise project.

    Accepts an object, filepath, or Path. If a file exists, inspects content
    and jsonpickle representation. Rejects unsupported XML files.
    """
    type_name = type(target).__name__
    module_name = getattr(type(target), "__module__", "")
    if type_name == "DenoiseProject" or "project_denoise" in module_name:
        return TYPE_DENOISE
    if type_name == "Project" and "project" in module_name:
        return TYPE_STARTRAILS

    if isinstance(target, (str, Path)):
        path = Path(target)
        if not path.exists():
            return detect_project_type_from_path(path)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = path.read_text(encoding="latin-1")
            except Exception as e:
                raise InvalidProjectError(f"Could not read project file {path}: {e}") from e

        stripped = raw_text.strip()
        if stripped.startswith("<?xml") or stripped.startswith("<project") or path.suffix.lower() == ".xml":
            raise UnsupportedProjectError(
                f"Unsupported XML project file: '{path.name}'. XML project files are not supported."
            )

        if not stripped.startswith("{"):
            raise InvalidProjectError(f"File '{path}' does not contain valid JSON project content.")

        try:
            decoded = jsonpickle.decode(raw_text)
        except Exception as e:
            raise InvalidProjectError(f"Could not decode project file {path}: {e}") from e

        if decoded is None:
            raise InvalidProjectError(f"Empty or null project content in {path}")

        dec_type = type(decoded).__name__
        if dec_type == "DenoiseProject":
            return TYPE_DENOISE
        if dec_type == "Project":
            return TYPE_STARTRAILS

        if isinstance(decoded, dict):
            py_obj = str(decoded.get("py/object", ""))
            if "DenoiseProject" in py_obj or "project_denoise" in py_obj:
                return TYPE_DENOISE
            if "Project" in py_obj:
                return TYPE_STARTRAILS
            if "star_files" in decoded:
                return TYPE_DENOISE
            if "rawInputFiles" in decoded:
                return TYPE_STARTRAILS

        raise InvalidProjectError(
            f"File '{path}' does not contain a recognized StarTrails or Denoise project (got {dec_type})."
        )

    raise InvalidProjectError(f"Cannot determine project type for {target}")
