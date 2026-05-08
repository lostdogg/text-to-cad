"""System and capability endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from ..features import capability_matrix
from ..metadata import APP_LICENSE, APP_METADATA, APP_VERSION

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/capabilities")
async def get_capabilities() -> Dict[str, Any]:
    return {
        "version": APP_VERSION,
        "license": APP_LICENSE,
        "metadata": APP_METADATA,
        "capabilities": capability_matrix(),
    }
