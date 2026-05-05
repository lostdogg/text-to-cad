"""Abstract base class for manufacturing optimizers."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import trimesh

from ..models.manufacturing import CostEstimate, TimeEstimate, ValidationResult


class OptimizationResult:
    def __init__(self, success: bool, notes: str = "", data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.notes = notes
        self.data = data or {}

    def dict(self) -> Dict[str, Any]:
        return {"success": self.success, "notes": self.notes, "data": self.data}


class BaseManufacturingOptimizer(ABC):
    """Abstract optimizer that every manufacturing process must implement."""

    @abstractmethod
    def optimize(self, mesh: trimesh.Trimesh) -> OptimizationResult:
        """Analyse and optimise mesh for the given manufacturing process."""
        ...

    @abstractmethod
    def estimate_cost(self, mesh: trimesh.Trimesh, params: Any) -> CostEstimate:
        """Estimate the monetary cost of manufacturing this mesh."""
        ...

    @abstractmethod
    def estimate_time(self, mesh: trimesh.Trimesh, params: Any) -> TimeEstimate:
        """Estimate the time needed to manufacture this mesh."""
        ...

    # ------------------------------------------------------------------ #
    # Shared utilities                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def bounding_box_volume(mesh: trimesh.Trimesh) -> float:
        """Return the axis-aligned bounding box volume in mm³."""
        if mesh.bounds is None:
            return 0.0
        size = mesh.bounds[1] - mesh.bounds[0]
        return float(size[0] * size[1] * size[2])

    @staticmethod
    def mesh_volume(mesh: trimesh.Trimesh) -> float:
        """Return mesh volume in mm³ (0 if not watertight)."""
        if mesh.is_volume:
            return float(abs(mesh.volume))
        return 0.0

    @staticmethod
    def surface_area(mesh: trimesh.Trimesh) -> float:
        return float(mesh.area)
