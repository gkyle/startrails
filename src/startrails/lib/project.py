"""Backward-compatibility re-export for jsonpickle deserialization of Project."""

from __future__ import annotations
from startrails.lib.project_startrails import EMPTY_CORRECTIONS_SIGNATURE, Project

__all__ = ["EMPTY_CORRECTIONS_SIGNATURE", "Project"]
