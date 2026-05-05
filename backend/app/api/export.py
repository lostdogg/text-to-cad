"""Export API router: STL, OBJ, STEP, G-code, QC reports, procurement specs."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ..cad.exporter import CADExporter
from ..config import settings
from ..models.manufacturing import CNCParams, LaserParams, PrintParams, ValidationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])
exporter = CADExporter()


def _get_mesh(model_id: str):
    """Retrieve trimesh from the in-memory model store."""
    from .generate import get_model_store
    models = get_model_store()
    if model_id not in models:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    model = models[model_id]
    if model.mesh_data is None:
        raise HTTPException(status_code=400, detail="Model has no mesh data")
    return model.mesh_data.to_trimesh(), model


def _export_dir() -> str:
    d = os.path.abspath(settings.EXPORT_DIR)
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------ #
# Mesh exports                                                        #
# ------------------------------------------------------------------ #

@router.post("/stl/{model_id}")
async def export_stl(model_id: str, binary: bool = True):
    mesh, model = _get_mesh(model_id)
    filepath = os.path.join(_export_dir(), f"{model_id}.stl")
    exporter.export_stl(mesh, filepath, binary=binary)
    return FileResponse(filepath, media_type="application/octet-stream",
                        filename=f"{model.name}.stl")


@router.post("/obj/{model_id}")
async def export_obj(model_id: str):
    mesh, model = _get_mesh(model_id)
    filepath = os.path.join(_export_dir(), f"{model_id}.obj")
    exporter.export_obj(mesh, filepath)
    return FileResponse(filepath, media_type="text/plain",
                        filename=f"{model.name}.obj")


@router.post("/step/{model_id}")
async def export_step(model_id: str):
    mesh, model = _get_mesh(model_id)
    filepath = os.path.join(_export_dir(), f"{model_id}.step")
    exporter.export_step(mesh, filepath)
    return FileResponse(filepath, media_type="text/plain",
                        filename=f"{model.name}.step")


# ------------------------------------------------------------------ #
# G-code exports                                                      #
# ------------------------------------------------------------------ #

class CNCExportRequest(BaseModel):
    params: Optional[CNCParams] = None


class PrintExportRequest(BaseModel):
    params: Optional[PrintParams] = None


class LaserExportRequest(BaseModel):
    params: Optional[LaserParams] = None


@router.post("/gcode/cnc/{model_id}")
async def export_gcode_cnc(model_id: str, request: Optional[CNCExportRequest] = None):
    mesh, model = _get_mesh(model_id)
    params = (request.params if request and request.params else None) or CNCParams()
    filepath = os.path.join(_export_dir(), f"{model_id}_cnc.gcode")
    exporter.export_gcode_cnc(mesh, filepath, params)
    return FileResponse(filepath, media_type="text/plain",
                        filename=f"{model.name}_cnc.gcode")


@router.post("/gcode/3dprint/{model_id}")
async def export_gcode_3dprint(model_id: str, request: Optional[PrintExportRequest] = None):
    mesh, model = _get_mesh(model_id)
    params = (request.params if request and request.params else None) or PrintParams()
    filepath = os.path.join(_export_dir(), f"{model_id}_print.gcode")
    exporter.export_gcode_3dprint(mesh, filepath, params)
    return FileResponse(filepath, media_type="text/plain",
                        filename=f"{model.name}_print.gcode")


@router.post("/gcode/laser/{model_id}")
async def export_gcode_laser(model_id: str, request: Optional[LaserExportRequest] = None):
    mesh, model = _get_mesh(model_id)
    params = (request.params if request and request.params else None) or LaserParams()
    from ..manufacturing.laser_cutting import LaserOptimizer
    opt = LaserOptimizer()
    profile = opt.extract_profile(mesh)
    filepath = os.path.join(_export_dir(), f"{model_id}_laser.gcode")
    exporter.export_gcode_laser(profile, filepath, params)
    return FileResponse(filepath, media_type="text/plain",
                        filename=f"{model.name}_laser.gcode")


# ------------------------------------------------------------------ #
# Reports                                                             #
# ------------------------------------------------------------------ #

@router.get("/report/{model_id}")
async def get_qc_report(model_id: str) -> Dict[str, Any]:
    """Generate and return a QC report for the model."""
    mesh, model = _get_mesh(model_id)
    from ..agents.validation_agent import ValidationAgent
    agent = ValidationAgent()
    validation = await agent.validate_mesh(mesh)
    report = exporter.generate_qc_report(mesh, validation)
    report["model_id"] = model_id
    report["model_name"] = model.name
    return report


@router.get("/procurement/{model_id}")
async def get_procurement_specs(
    model_id: str,
    materials: Optional[str] = "aluminum_6061",
) -> Dict[str, Any]:
    """Return procurement specifications with McMaster-Carr / DigiKey part numbers."""
    _, model = _get_mesh(model_id)
    from ..agents.validation_agent import ValidationAgent
    mesh, _ = _get_mesh(model_id)
    agent = ValidationAgent()
    validation = await agent.validate_mesh(mesh)
    mat_list = [m.strip() for m in (materials or "aluminum_6061").split(",")]
    specs = exporter.generate_procurement_specs(validation, mat_list)
    specs["model_id"] = model_id
    specs["model_name"] = model.name
    return specs
