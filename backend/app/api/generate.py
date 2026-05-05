"""API router for text-to-CAD generation."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agents.coordinator import AgentCoordinator
from ..config import settings
from ..models.geometry import CADModel, MeshData
from ..models.manufacturing import ManufacturingReport, ValidationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])

# In-memory model store (use a DB in production)
_models: Dict[str, CADModel] = {}
_coordinator: Optional[AgentCoordinator] = None


def get_coordinator() -> AgentCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator(openai_api_key=settings.OPENAI_API_KEY)
    return _coordinator


# ------------------------------------------------------------------ #
# Request / Response schemas                                          #
# ------------------------------------------------------------------ #

class GenerateRequest(BaseModel):
    text: str
    manufacturing_type: Optional[str] = None
    options: Dict[str, Any] = {}


class GenerateResponse(BaseModel):
    model_id: str
    name: str
    mesh_data: Optional[MeshData] = None
    validation: Optional[ValidationResult] = None
    manufacturing_report: Optional[ManufacturingReport] = None
    processing_time: float = 0.0
    agent_logs: List[str] = []
    success: bool = True
    error: Optional[str] = None


# ------------------------------------------------------------------ #
# Endpoints                                                           #
# ------------------------------------------------------------------ #

@router.post("", response_model=GenerateResponse)
async def generate_model(request: GenerateRequest) -> GenerateResponse:
    """Convert a natural language description to a 3D CAD model."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    coordinator = get_coordinator()
    result = await coordinator.process(
        text=request.text,
        manufacturing_type=request.manufacturing_type,
        options=request.options,
    )

    if result.success and result.model:
        _models[result.model.id] = result.model

    return GenerateResponse(
        model_id=result.task_id,
        name=result.model.name if result.model else "",
        mesh_data=result.model.mesh_data if result.model else None,
        validation=result.validation,
        manufacturing_report=result.manufacturing_report,
        processing_time=result.processing_time,
        agent_logs=result.agent_logs,
        success=result.success,
        error=result.error,
    )


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """List all generated models."""
    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "created_at": m.created_at.isoformat(),
                "vertex_count": m.mesh_data.vertex_count if m.mesh_data else 0,
                "face_count": m.mesh_data.face_count if m.mesh_data else 0,
            }
            for m in _models.values()
        ],
        "total": len(_models),
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> CADModel:
    """Get a specific model by ID."""
    if model_id not in _models:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return _models[model_id]


def get_model_store() -> Dict[str, CADModel]:
    return _models
