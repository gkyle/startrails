"""Backward-compatibility re-export for jsonpickle deserialization of FinishProject."""

from startrails.lib.project_split import SplitProject as FinishProject

__all__ = ["FinishProject"]
