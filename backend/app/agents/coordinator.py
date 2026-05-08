"""Multi-agent coordinator: orchestrates NLP, CSG, and Validation agents."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..models.ai_provider import AIProviderConfig
from ..models.geometry import CADModel, GeometrySpec, MeshData
from ..models.manufacturing import ManufacturingReport, ValidationResult
from .csg_agent import CSGAgent, ComplexityError
from .nlp_agent import NLPAgent
from .services import ManufacturingService, SolidGenerationService, ValidationService
from .validation_agent import ValidationAgent

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class StageMetric:
    """Timing and outcome for a single pipeline stage."""
    name: str
    duration_ms: float = 0.0
    success: bool = True
    error_code: Optional[str] = None
    notes: str = ""


@dataclass
class PipelineTelemetry:
    """Structured per-stage telemetry for a full pipeline run."""
    task_id: str = ""
    stages: List[StageMetric] = field(default_factory=list)
    total_duration_ms: float = 0.0
    parse_confidence: float = 1.0
    parse_warnings: List[str] = field(default_factory=list)
    primitive_count: int = 0
    operation_count: int = 0
    complexity_score: int = 0
    mesh_face_count: int = 0
    mesh_vertex_count: int = 0
    validation_error_count: int = 0
    validation_warning_count: int = 0


@dataclass
class AgentTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: TaskPriority = TaskPriority.NORMAL
    text: str = ""
    manufacturing_type: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    ai_provider: Optional[AIProviderConfig] = None


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
    telemetry: Optional[PipelineTelemetry] = None


class AgentCoordinator:
    """Orchestrate multi-agent workflow: NLP -> CSG -> Validation -> Manufacturing."""

    def __init__(self, openai_api_key: Optional[str] = None):
        self.nlp_agent = NLPAgent(openai_api_key=openai_api_key)
        self.csg_agent = CSGAgent()
        self.validation_agent = ValidationAgent()
        self.solid_service = SolidGenerationService(self.nlp_agent, self.csg_agent)
        self.validation_service = ValidationService(self.validation_agent)
        self.manufacturing_service = ManufacturingService()
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._results: Dict[str, CoordinatorResult] = {}

    async def process(
        self,
        text: str,
        manufacturing_type: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        ai_provider: Optional[AIProviderConfig] = None,
    ) -> CoordinatorResult:
        """Run the full agent pipeline for a text-to-CAD request."""
        task = AgentTask(
            text=text,
            manufacturing_type=manufacturing_type,
            options=options or {},
            ai_provider=ai_provider,
        )
        return await self._run_pipeline(task)

    async def _run_pipeline(self, task: AgentTask) -> CoordinatorResult:
        """Execute the NLP -> CSG -> Validate pipeline."""
        wall_start = time.monotonic()
        logs: List[str] = []
        telemetry = PipelineTelemetry(task_id=task.task_id)

        # ---------------------------------------------------------------- #
        # Step 1: NLP parsing                                               #
        # ---------------------------------------------------------------- #
        t0 = time.monotonic()
        try:
            logs.append("NLPAgent: parsing text...")
            geometry_spec: GeometrySpec = await self.solid_service.parse_text(
                task.text, provider_config=task.ai_provider
            )
            dur = (time.monotonic() - t0) * 1000
            logs.append(
                f"NLPAgent: found {len(geometry_spec.primitives)} primitive(s), "
                f"{len(geometry_spec.operations)} operation(s), "
                f"confidence={geometry_spec.parse_confidence:.2f}"
            )
            if geometry_spec.warnings:
                for w in geometry_spec.warnings:
                    logs.append(f"NLPAgent [WARN]: {w}")
            telemetry.stages.append(StageMetric(name="nlp", duration_ms=round(dur, 1)))
            telemetry.parse_confidence = geometry_spec.parse_confidence
            telemetry.parse_warnings = geometry_spec.warnings
            telemetry.primitive_count = len(geometry_spec.primitives)
            telemetry.operation_count = len(geometry_spec.operations)
            telemetry.complexity_score = geometry_spec.complexity_score
        except Exception as exc:
            dur = (time.monotonic() - t0) * 1000
            telemetry.stages.append(StageMetric(
                name="nlp", duration_ms=round(dur, 1),
                success=False, error_code="NLP_FAILED",
            ))
            logger.exception("NLPAgent failed")
            return CoordinatorResult(
                task_id=task.task_id,
                success=False,
                error=f"NLP parsing failed: {exc}",
                processing_time=time.monotonic() - wall_start,
                agent_logs=logs,
                telemetry=telemetry,
            )

        # ---------------------------------------------------------------- #
        # Step 2: CSG build                                                 #
        # ---------------------------------------------------------------- #
        t0 = time.monotonic()
        try:
            logs.append("CSGAgent: building mesh...")
            mesh_data: MeshData = await self.solid_service.build_mesh(geometry_spec)
            dur = (time.monotonic() - t0) * 1000
            logs.append(
                f"CSGAgent: mesh built — "
                f"{mesh_data.vertex_count} vertices, {mesh_data.face_count} faces"
            )
            telemetry.stages.append(StageMetric(name="csg", duration_ms=round(dur, 1)))
            telemetry.mesh_face_count = mesh_data.face_count
            telemetry.mesh_vertex_count = mesh_data.vertex_count
        except ComplexityError as exc:
            dur = (time.monotonic() - t0) * 1000
            telemetry.stages.append(StageMetric(
                name="csg", duration_ms=round(dur, 1),
                success=False, error_code="COMPLEXITY_LIMIT",
            ))
            return CoordinatorResult(
                task_id=task.task_id,
                success=False,
                error=f"Complexity limit exceeded: {exc}",
                processing_time=time.monotonic() - wall_start,
                agent_logs=logs,
                telemetry=telemetry,
            )
        except Exception as exc:
            dur = (time.monotonic() - t0) * 1000
            telemetry.stages.append(StageMetric(
                name="csg", duration_ms=round(dur, 1),
                success=False, error_code="CSG_FAILED",
            ))
            logger.exception("CSGAgent failed")
            return CoordinatorResult(
                task_id=task.task_id,
                success=False,
                error=f"CSG build failed: {exc}",
                processing_time=time.monotonic() - wall_start,
                agent_logs=logs,
                telemetry=telemetry,
            )

        # ---------------------------------------------------------------- #
        # Step 3: Validation                                                #
        # ---------------------------------------------------------------- #
        t0 = time.monotonic()
        validation: Optional[ValidationResult] = None
        try:
            logs.append("ValidationAgent: validating mesh...")
            validation = await self.validation_service.validate_mesh(
                mesh_data, task.manufacturing_type
            )
            dur = (time.monotonic() - t0) * 1000
            logs.append(
                f"ValidationAgent: valid={validation.is_valid}, "
                f"errors={validation.error_count()}, warnings={validation.warning_count()}"
            )
            if validation.remediation_hints:
                for hint in validation.remediation_hints:
                    logs.append(f"ValidationAgent [HINT]: {hint}")
            telemetry.stages.append(StageMetric(name="validation", duration_ms=round(dur, 1)))
            telemetry.validation_error_count = validation.error_count()
            telemetry.validation_warning_count = validation.warning_count()
        except Exception as exc:
            dur = (time.monotonic() - t0) * 1000
            telemetry.stages.append(StageMetric(
                name="validation", duration_ms=round(dur, 1),
                success=False, error_code="VALIDATION_FAILED", notes=str(exc),
            ))
            logger.warning("ValidationAgent failed (non-fatal): %s", exc)
            logs.append(f"ValidationAgent: failed ({exc})")

        # ---------------------------------------------------------------- #
        # Step 4: Manufacturing report                                      #
        # ---------------------------------------------------------------- #
        mfg_report: Optional[ManufacturingReport] = None
        if task.manufacturing_type:
            t0 = time.monotonic()
            mfg_report = await self._build_manufacturing_report(
                mesh_data, task.manufacturing_type, validation, task.task_id, logs
            )
            dur = (time.monotonic() - t0) * 1000
            telemetry.stages.append(StageMetric(name="manufacturing", duration_ms=round(dur, 1)))

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

        elapsed = time.monotonic() - wall_start
        telemetry.total_duration_ms = round(elapsed * 1000, 1)
        logs.append(f"Pipeline completed in {elapsed:.2f}s")
        result = CoordinatorResult(
            task_id=task.task_id,
            success=True,
            model=model,
            validation=validation,
            manufacturing_report=mfg_report,
            processing_time=round(elapsed, 3),
            agent_logs=logs,
            telemetry=telemetry,
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
        try:
            return await self.manufacturing_service.create_report(
                mesh_data=mesh_data,
                manufacturing_type=manufacturing_type,
                validation=validation,
                model_id=model_id,
                logs=logs,
            )
        except Exception as exc:
            logger.warning("Manufacturing report generation failed: %s", exc)
            return ManufacturingReport(model_id=model_id, validation=validation)

    @staticmethod
    def _infer_name(text: str) -> str:
        """Derive a short model name from the input text."""
        words = text.strip().split()[:5]
        name = " ".join(w.capitalize() for w in words)
        return name or "Untitled Model"
