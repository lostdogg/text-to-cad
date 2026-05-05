"""Pydantic models for manufacturing processes, parameters, and results."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ManufacturingType(str, Enum):
    CNC_3AXIS = "cnc_3axis"
    PRINTING_3D = "3d_printing"
    LASER_CUTTING = "laser_cutting"


class MaterialType(str, Enum):
    METAL = "metal"
    PLASTIC = "plastic"
    WOOD = "wood"
    COMPOSITE = "composite"
    SHEET = "sheet"


class Material(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    name: str
    type: MaterialType
    hardness: float = 0.0          # HRC or Brinell depending on context
    cost_per_unit: float = 0.0     # USD per kg or per sheet
    density: float = 1.0           # g/cm³
    melting_point: Optional[float] = None  # °C
    notes: str = ""


# --------------------------------------------------------------------------- #
# Process parameters                                                            #
# --------------------------------------------------------------------------- #

class CNCParams(BaseModel):
    tool_diameter: float = 6.0         # mm
    spindle_speed: int = 10000         # RPM
    feed_rate: float = 1000.0          # mm/min
    depth_of_cut: float = 1.0          # mm
    material: str = "aluminum"
    operations: List[str] = Field(
        default_factory=lambda: ["facing", "contouring"]
    )
    coolant: bool = True
    stock_allowance: float = 0.5       # mm


class PrintParams(BaseModel):
    layer_height: float = 0.2          # mm
    infill_percent: float = 20.0       # %
    supports: bool = True
    material: str = "PLA"
    printer_type: str = "FDM"
    nozzle_diameter: float = 0.4       # mm
    print_speed: float = 60.0          # mm/s
    bed_temperature: float = 60.0      # °C
    nozzle_temperature: float = 200.0  # °C
    wall_count: int = 3


class LaserParams(BaseModel):
    power: float = 80.0                # %
    speed: float = 20.0                # mm/s
    kerf_width: float = 0.2            # mm
    material: str = "acrylic"
    passes: int = 1
    focus_offset: float = 0.0         # mm
    air_assist: bool = True
    sheet_thickness: float = 3.0       # mm


# --------------------------------------------------------------------------- #
# Validation                                                                    #
# --------------------------------------------------------------------------- #

class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    severity: IssueSeverity
    code: str
    message: str
    location: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None


class MeshStats(BaseModel):
    vertex_count: int = 0
    face_count: int = 0
    volume: float = 0.0               # mm³
    surface_area: float = 0.0         # mm²
    bounding_box: Dict[str, float] = Field(default_factory=dict)
    is_watertight: bool = False
    is_manifold: bool = False


class ValidationResult(BaseModel):
    is_valid: bool = True
    issues: List[ValidationIssue] = Field(default_factory=list)
    mesh_stats: MeshStats = Field(default_factory=MeshStats)
    manufacturing_type: Optional[str] = None
    min_wall_thickness: Optional[float] = None
    max_overhang_angle: Optional[float] = None

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)


# --------------------------------------------------------------------------- #
# Cost & time estimates                                                         #
# --------------------------------------------------------------------------- #

class CostEstimate(BaseModel):
    material_cost: float = 0.0         # USD
    machine_cost: float = 0.0          # USD
    labour_cost: float = 0.0           # USD
    total_cost: float = 0.0            # USD
    currency: str = "USD"
    notes: str = ""


class TimeEstimate(BaseModel):
    setup_time: float = 0.0            # minutes
    machining_time: float = 0.0        # minutes
    total_time: float = 0.0            # minutes
    notes: str = ""


# --------------------------------------------------------------------------- #
# Full manufacturing report                                                     #
# --------------------------------------------------------------------------- #

class ManufacturingReport(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    model_id: str = ""
    validation: Optional[ValidationResult] = None
    cnc_params: Optional[CNCParams] = None
    print_params: Optional[PrintParams] = None
    laser_params: Optional[LaserParams] = None
    cost_estimate: Optional[CostEstimate] = None
    time_estimate: Optional[TimeEstimate] = None
    recommended_type: Optional[ManufacturingType] = None
    notes: str = ""
