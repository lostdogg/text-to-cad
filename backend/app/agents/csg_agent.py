"""CSG Agent: wraps CSGOperations and ManifoldResolver with async interface."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import trimesh

from ..cad.csg_operations import CSGOperations
from ..cad.manifold import ManifoldResolver, ManifoldResult
from ..models.geometry import (
    BooleanOpSpec,
    BooleanOpType,
    GeometrySpec,
    MeshData,
    PrimitiveSpec,
    PrimitiveType,
    Transform,
)

logger = logging.getLogger(__name__)

# Complexity limits (raise ValueError when exceeded)
_MAX_PRIMITIVES = 50
_MAX_OPERATIONS = 30
_MAX_OPERATION_DEPTH = 20
_MAX_RESULT_FACES = 500_000


class ComplexityError(ValueError):
    """Raised when a GeometrySpec exceeds safe complexity limits."""


class CSGAgent:
    """Asynchronous CSG operation agent."""

    def __init__(self):
        self.csg = CSGOperations()
        self.resolver = ManifoldResolver()

    async def build_from_spec(self, spec: GeometrySpec) -> MeshData:
        """Build a mesh from a GeometrySpec, running CSG ops in an executor."""
        self._check_complexity(spec)
        loop = asyncio.get_event_loop()
        mesh = await loop.run_in_executor(None, self._build_sync, spec)
        return MeshData.from_trimesh(mesh)

    def _check_complexity(self, spec: GeometrySpec) -> None:
        """Guard against unreasonably complex specs that would OOM or hang."""
        if len(spec.primitives) > _MAX_PRIMITIVES:
            raise ComplexityError(
                f"Too many primitives ({len(spec.primitives)} > {_MAX_PRIMITIVES}). "
                "Simplify the request or split it into multiple models."
            )
        if len(spec.operations) > _MAX_OPERATIONS:
            raise ComplexityError(
                f"Too many operations ({len(spec.operations)} > {_MAX_OPERATIONS})."
            )
        depth = self._operation_depth(spec)
        if depth > _MAX_OPERATION_DEPTH:
            raise ComplexityError(
                f"Operation chain depth {depth} exceeds limit {_MAX_OPERATION_DEPTH}."
            )

    @staticmethod
    def _operation_depth(spec: GeometrySpec) -> int:
        """Compute the maximum chain depth of the operation DAG."""
        if not spec.operations:
            return 0
        # depth[i] = 0 for primitive, computed for operation results
        n = len(spec.primitives)
        depth: Dict[int, int] = {i: 0 for i in range(n)}
        for op_idx, op in enumerate(spec.operations):
            result_idx = n + op_idx
            da = depth.get(op.operand_a, 0) if isinstance(op.operand_a, int) else 0
            db = depth.get(op.operand_b, 0) if isinstance(op.operand_b, int) else 0
            depth[result_idx] = max(da, db) + 1
        return max(depth.values()) if depth else 0

    def _build_sync(self, spec: GeometrySpec) -> trimesh.Trimesh:
        """Synchronous mesh build (runs in thread pool)."""
        if not spec.primitives:
            return self._create_default_mesh()

        # Build primitive meshes
        meshes: List[trimesh.Trimesh] = []
        for prim in spec.primitives:
            m = self._build_primitive(prim)
            # Apply transform
            m = CSGOperations.apply_transform(
                m,
                position=prim.transform.position.to_list(),
                rotation_deg=prim.transform.rotation.to_list(),
                scale=prim.transform.scale.to_list(),
            )
            # Sanity check individual primitive
            if len(m.faces) == 0:
                logger.warning("Primitive '%s' produced empty mesh; using default cube", prim.name)
                m = CSGOperations.create_box(10, 10, 10)
            meshes.append(m)

        if not spec.operations:
            # No boolean ops: union all primitives
            result = meshes[0]
            for m in meshes[1:]:
                result = self._boolean_with_checks(result, m, BooleanOpType.UNION)
        else:
            result = self._apply_operations(meshes, spec.operations)

        # Guard against pathologically large meshes
        if len(result.faces) > _MAX_RESULT_FACES:
            logger.warning(
                "Result mesh has %d faces (limit %d); decimating for safety",
                len(result.faces), _MAX_RESULT_FACES,
            )
            try:
                target = _MAX_RESULT_FACES // 2
                result = result.simplify_quadric_decimation(target)
            except Exception as exc:
                logger.warning("Decimation failed: %s", exc)

        # Resolve manifold issues
        resolved: ManifoldResult = self.resolver.resolve(result)
        if resolved.issues_found:
            logger.info("Manifold issues resolved: %s", resolved.issues_fixed)
        return resolved.mesh

    def _build_primitive(self, prim: PrimitiveSpec) -> trimesh.Trimesh:
        """Create a trimesh from a PrimitiveSpec."""
        d = prim.dimensions
        ptype = PrimitiveType(prim.type) if isinstance(prim.type, str) else prim.type
        if ptype == PrimitiveType.BOX:
            return self.csg.create_box(
                width=d.get("width", 10.0),
                height=d.get("height", 10.0),
                depth=d.get("depth", 10.0),
            )
        if ptype == PrimitiveType.CYLINDER:
            return self.csg.create_cylinder(
                radius=d.get("radius", 5.0),
                height=d.get("height", 20.0),
            )
        if ptype == PrimitiveType.SPHERE:
            return self.csg.create_sphere(radius=d.get("radius", 10.0))
        if ptype == PrimitiveType.CONE:
            return self.csg.create_cone(
                radius=d.get("radius", 5.0),
                height=d.get("height", 10.0),
            )
        if ptype == PrimitiveType.TORUS:
            return self.csg.create_torus(
                major_radius=d.get("major_radius", 15.0),
                minor_radius=d.get("minor_radius", 4.0),
            )
        raise ValueError(f"Unknown primitive type: {ptype}")

    def _boolean_with_checks(
        self,
        mesh_a: trimesh.Trimesh,
        mesh_b: trimesh.Trimesh,
        op_type: BooleanOpType,
    ) -> trimesh.Trimesh:
        """Run a boolean op with pre/post sanity checks."""
        # Pre-boolean: ensure both meshes have geometry
        if len(mesh_a.faces) == 0:
            logger.warning("Operand A is empty; returning operand B")
            return mesh_b
        if len(mesh_b.faces) == 0:
            logger.warning("Operand B is empty; returning operand A")
            return mesh_a

        # Pre-boolean: non-intersecting subtraction/intersection is degenerate
        if op_type in (BooleanOpType.SUBTRACTION, BooleanOpType.INTERSECTION):
            if not self._meshes_overlap(mesh_a, mesh_b):
                if op_type == BooleanOpType.SUBTRACTION:
                    logger.info("Subtraction operands do not overlap; returning mesh_a unchanged")
                    return mesh_a.copy()
                else:
                    logger.info("Intersection operands do not overlap; returning empty mesh")
                    return CSGOperations.create_box(0.001, 0.001, 0.001)

        if op_type == BooleanOpType.UNION:
            result = self.csg.union(mesh_a, mesh_b)
        elif op_type == BooleanOpType.INTERSECTION:
            result = self.csg.intersection(mesh_a, mesh_b)
        else:
            result = self.csg.subtraction(mesh_a, mesh_b)

        # Post-boolean: warn if result is suspiciously small
        if len(result.faces) > 0 and len(result.faces) < 4:
            logger.warning(
                "Boolean %s produced only %d face(s); mesh may be degenerate",
                op_type, len(result.faces),
            )

        return result

    @staticmethod
    def _meshes_overlap(mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> bool:
        """Quick AABB overlap test to detect non-intersecting operands."""
        try:
            if mesh_a.bounds is None or mesh_b.bounds is None:
                return True  # Unknown: assume overlap
            for i in range(3):
                if mesh_a.bounds[1][i] < mesh_b.bounds[0][i] or \
                   mesh_b.bounds[1][i] < mesh_a.bounds[0][i]:
                    return False
            return True
        except Exception:
            return True  # Default to allowing the operation

    def _apply_operations(
        self,
        meshes: List[trimesh.Trimesh],
        operations: List[BooleanOpSpec],
    ) -> trimesh.Trimesh:
        """Apply boolean operations in dependency order, with per-op validation."""
        result_map: Dict[int, trimesh.Trimesh] = {i: m for i, m in enumerate(meshes)}
        op_counter = len(meshes)

        for op in operations:
            mesh_a = self._resolve_operand(op.operand_a, result_map, op_counter)
            mesh_b = self._resolve_operand(op.operand_b, result_map, op_counter)
            op_type = BooleanOpType(op.operation) if isinstance(op.operation, str) else op.operation
            result = self._boolean_with_checks(mesh_a, mesh_b, op_type)
            result_map[op_counter] = result
            op_counter += 1

        # Return the last result
        return result_map[op_counter - 1]

    @staticmethod
    def _resolve_operand(
        operand: Any,
        result_map: Dict[int, trimesh.Trimesh],
        next_idx: int,
    ) -> trimesh.Trimesh:
        """Resolve an operand index to a mesh, with a helpful error message."""
        if isinstance(operand, int):
            if operand in result_map:
                return result_map[operand]
            raise ValueError(
                f"Operand index {operand} not found in result map "
                f"(available: {sorted(result_map.keys())}). "
                "Check that operand indices are correct and operations are ordered correctly."
            )
        raise TypeError(f"Unsupported operand type: {type(operand)}")

    @staticmethod
    def _create_default_mesh() -> trimesh.Trimesh:
        return CSGOperations.create_box(10, 10, 10)

    async def process_operation(
        self,
        operation_type: str,
        operand_specs: List[GeometrySpec],
    ) -> MeshData:
        """Process a standalone boolean operation on two geometry specs."""
        if len(operand_specs) < 2:
            raise ValueError("Need at least 2 operands for a boolean operation")
        loop = asyncio.get_event_loop()

        def _run():
            agent = CSGAgent()
            meshes = [agent._build_sync(s) for s in operand_specs]
            op = BooleanOpType(operation_type)
            result = agent._boolean_with_checks(meshes[0], meshes[1], op)
            resolved = agent.resolver.resolve(result)
            return resolved.mesh

        mesh = await loop.run_in_executor(None, _run)
        return MeshData.from_trimesh(mesh)
