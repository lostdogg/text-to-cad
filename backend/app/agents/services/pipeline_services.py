"""Narrow service interfaces for pipeline stages."""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...models.ai_provider import AIProviderConfig
from ...models.geometry import GeometrySpec, MeshData
from ...models.manufacturing import ManufacturingReport, ManufacturingType, ValidationResult
from ..csg_agent import CSGAgent
from ..nlp_agent import NLPAgent
from ..validation_agent import ValidationAgent


class SolidGenerationService:
    """Service for text parsing and solid mesh construction."""

    def __init__(self, nlp_agent: NLPAgent, csg_agent: CSGAgent):
        self._nlp_agent = nlp_agent
        self._csg_agent = csg_agent

    async def parse_text(
        self, text: str, provider_config: Optional[AIProviderConfig]
    ) -> GeometrySpec:
        return await self._nlp_agent.parse_text(text, provider_config=provider_config)

    async def build_mesh(self, spec: GeometrySpec) -> MeshData:
        return await self._csg_agent.build_from_spec(spec)


class ValidationService:
    """Service for mesh validation."""

    def __init__(self, validation_agent: ValidationAgent):
        self._validation_agent = validation_agent

    async def validate_mesh(
        self, mesh_data: MeshData, manufacturing_type: Optional[str]
    ) -> ValidationResult:
        mesh = mesh_data.to_trimesh()
        return await self._validation_agent.validate_mesh(mesh, manufacturing_type)


class ManufacturingService:
    """Service for manufacturing reports."""

    async def create_report(
        self,
        mesh_data: MeshData,
        manufacturing_type: str,
        validation: Optional[ValidationResult],
        model_id: str,
        logs: List[str],
    ) -> ManufacturingReport:
        from ...manufacturing.cnc import CNCOptimizer
        from ...manufacturing.laser_cutting import LaserOptimizer
        from ...manufacturing.printing_3d import PrintingOptimizer
        from ...models.manufacturing import CNCParams, LaserParams, PrintParams

        mesh = mesh_data.to_trimesh()
        report = ManufacturingReport(model_id=model_id, validation=validation)

        try:
            mfg = ManufacturingType(manufacturing_type)
            if mfg == ManufacturingType.CNC_3AXIS:
                opt = CNCOptimizer()
                params = CNCParams()
                report.cnc_params = params
                report.cost_estimate = opt.estimate_cost(mesh, params)
                report.time_estimate = opt.estimate_time(mesh, params)
                report.recommended_type = mfg
                logs.append("ManufacturingReport: CNC estimates complete")
            elif mfg == ManufacturingType.PRINTING_3D:
                opt = PrintingOptimizer()
                params = PrintParams()
                report.print_params = params
                report.cost_estimate = opt.estimate_cost(mesh, params)
                report.time_estimate = opt.estimate_time(mesh, params)
                report.recommended_type = mfg
                logs.append("ManufacturingReport: 3D print estimates complete")
            elif mfg == ManufacturingType.LASER_CUTTING:
                opt = LaserOptimizer()
                params = LaserParams()
                report.laser_params = params
                report.cost_estimate = opt.estimate_cost(mesh, params)
                report.time_estimate = opt.estimate_time(mesh, params)
                report.recommended_type = mfg
                logs.append("ManufacturingReport: laser cutting estimates complete")
        except Exception as exc:
            logs.append(f"ManufacturingReport: failed ({exc})")

        return report
