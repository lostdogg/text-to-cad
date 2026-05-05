"""Multi-agent coordinator: orchestrates NLP, CSG, and Validation agents."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..models.geometry import CADModel, GeometrySpec, MeshData
from ..models.manufacturing import ManufacturingReport, ManufacturingType, ValidationResult
from .csg_agent import CSGAgent
from .nlp_agent import NLPAgent
from .validation_agent import ValidationAgent

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class AgentTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: TaskPriority = TaskPriority.NORMAL
    text: str = ""
    manufacturing_type: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoordinatorResult:
    task_id: str
    success: bool
    model: Optional[CADModel] = None
    validation: Optional[ValidationResult] = None
    manufacturing_report: Optional[ManufacturingReport] = None
    processing_time: float = 0.0
    error: Optional[str] = None
    agent_logs: List[str] = field(default_factory=list)


class AgentCoordinator:
    """Orchestrate multi-agent workflow: NLP -> CSG -> Validation -> Manufacturing."""

    def __init__(self, openai_api_key: Optional[str] = None):
        self.nlp_agent = NLPAgent(openai_api_key=openai_api_key)
        self.csg_agent = CSGAgent()
        self.validation_agent = ValidationAgent()
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._results: Dict[str, CoordinatorResult] = {}

    async def process(
        self,
        text: str,
        manufacturing_type: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> CoordinatorResult:
        """Run the full agent pipeline for a text-to-CAD request."""
        task = AgentTask(
            text=text,
            manufacturing_type=manufacturing_type,
            options=options or {},
        )
        return await self._run_pipeline(task)

    async def _run_pipeline(self, task: AgentTask) -> CoordinatorResult:
        """Execute the NLP -> CSG -> Validate pipeline."""
        start = time.monotonic()
        logs: List[str] = []

        # ---------------------------------------------------------------- #
        # Step 1: NLP parsing                                               #
        # ---------------------------------------------------------------- #
        try:
            logs.append("NLPAgent: parsing text...")
            geometry_spec: GeometrySpec = await self.nlp_agent.parse_text(task.text)
            logs.append(
                f"NLPAgent: found {len(geometry_spec.primitives)} primitive(s), "
                f"{len(geometry_spec.operations)} operation(s)"
            )
        except Exception as exc:
            logger.exception("NLPAgent failed")
            return CoordinatorResult(
                task_id=task.task_id,
                success=False,
                error=f"NLP parsing failed: {exc}",
                processing_time=time.monotonic() - start,
                agent_logs=logs,
            )

        # ---------------------------------------------------------------- #
        # Step 2: CSG build + Validation (parallel)                        #
        # ---------------------------------------------------------------- #
        try:
            logs.append("CSGAgent: building mesh...")
            csg_task = asyncio.create_task(
                self.csg_agent.build_from_spec(geometry_spec)
            )
            mesh_data: MeshData = await csg_task
            logs.append(
                f"CSGAgent: mesh built — "
                f"{mesh_data.vertex_count} vertices, {mesh_data.face_count} faces"
            )
        except Exception as exc:
            logger.exception("CSGAgent failed")
            return CoordinatorResult(
                task_id=task.task_id,
                success=False,
                error=f"CSG build failed: {exc}",
                processing_time=time.monotonic() - start,
                agent_logs=logs,
            )

        # ---------------------------------------------------------------- #
        # Step 3: Validation                                                #
        # ---------------------------------------------------------------- #
        validation: Optional[ValidationResult] = None
        try:
            logs.append("ValidationAgent: validating mesh...")
            trimesh_mesh = mesh_data.to_trimesh()
            validation = await self.validation_agent.validate_mesh(
                trimesh_mesh, task.manufacturing_type
            )
            logs.append(
                f"ValidationAgent: valid={validation.is_valid}, "
                f"errors={validation.error_count()}, warnings={validation.warning_count()}"
            )
        except Exception as exc:
            logger.warning("ValidationAgent failed (non-fatal): %s", exc)
            logs.append(f"ValidationAgent: failed ({exc})")

        # ---------------------------------------------------------------- #
        # Step 4: Manufacturing report                                      #
        # ---------------------------------------------------------------- #
        mfg_report: Optional[ManufacturingReport] = None
        if task.manufacturing_type:
            mfg_report = await self._build_manufacturing_report(
                mesh_data, task.manufacturing_type, validation, task.task_id, logs
            )

        # ---------------------------------------------------------------- #
        # Assemble result                                                   #
        # ---------------------------------------------------------------- #
        model = CADModel(
            id=task.task_id,
            name=self._infer_name(task.text),
            description=task.text,
            geometry_spec=geometry_spec,
            mesh_data=mesh_data,
            source_text=task.text,
        )

        elapsed = time.monotonic() - start
        logs.append(f"Pipeline completed in {elapsed:.2f}s")
        result = CoordinatorResult(
            task_id=task.task_id,
            success=True,
            model=model,
            validation=validation,
            manufacturing_report=mfg_report,
            processing_time=round(elapsed, 3),
            agent_logs=logs,
        )
        self._results[task.task_id] = result
        return result

    async def _build_manufacturing_report(
        self,
        mesh_data: MeshData,
        manufacturing_type: str,
        validation: Optional[ValidationResult],
        model_id: str,
        logs: List[str],
    ) -> ManufacturingReport:
        """Build a manufacturing report asynchronously."""
        from ..manufacturing.cnc import CNCOptimizer
        from ..manufacturing.printing_3d import PrintingOptimizer
        from ..manufacturing.laser_cutting import LaserOptimizer
        from ..models.manufacturing import CNCParams, PrintParams, LaserParams

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
            logger.warning("Manufacturing report generation failed: %s", exc)
            logs.append(f"ManufacturingReport: failed ({exc})")

        return report

    @staticmethod
    def _infer_name(text: str) -> str:
        """Derive a short model name from the input text."""
        words = text.strip().split()[:5]
        name = " ".join(w.capitalize() for w in words)
        return name or "Untitled Model"
