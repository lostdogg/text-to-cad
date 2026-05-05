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


class CSGAgent:
    """Asynchronous CSG operation agent."""

    def __init__(self):
        self.csg = CSGOperations()
        self.resolver = ManifoldResolver()

    async def build_from_spec(self, spec: GeometrySpec) -> MeshData:
        """Build a mesh from a GeometrySpec, running CSG ops in an executor."""
        loop = asyncio.get_event_loop()
        mesh = await loop.run_in_executor(None, self._build_sync, spec)
        return MeshData.from_trimesh(mesh)

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
            meshes.append(m)

        if not spec.operations:
            # No boolean ops: union all primitives
            result = meshes[0]
            for m in meshes[1:]:
                result = self.csg.union(result, m)
        else:
            result = self._apply_operations(meshes, spec.operations)

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

    def _apply_operations(
        self,
        meshes: List[trimesh.Trimesh],
        operations: List[BooleanOpSpec],
    ) -> trimesh.Trimesh:
        """Recursively apply boolean operations."""
        result_map: Dict[int, trimesh.Trimesh] = {i: m for i, m in enumerate(meshes)}
        op_counter = len(meshes)

        for op in operations:
            mesh_a = self._resolve_operand(op.operand_a, result_map)
            mesh_b = self._resolve_operand(op.operand_b, result_map)
            op_type = BooleanOpType(op.operation) if isinstance(op.operation, str) else op.operation
            if op_type == BooleanOpType.UNION:
                result = self.csg.union(mesh_a, mesh_b)
            elif op_type == BooleanOpType.INTERSECTION:
                result = self.csg.intersection(mesh_a, mesh_b)
            elif op_type == BooleanOpType.SUBTRACTION:
                result = self.csg.subtraction(mesh_a, mesh_b)
            else:
                result = mesh_a
            result_map[op_counter] = result
            op_counter += 1

        # Return the last result
        return result_map[op_counter - 1]

    @staticmethod
    def _resolve_operand(
        operand: Any,
        result_map: Dict[int, trimesh.Trimesh],
    ) -> trimesh.Trimesh:
        """Resolve an operand index to a mesh."""
        if isinstance(operand, int):
            if operand in result_map:
                return result_map[operand]
            raise ValueError(f"Operand index {operand} not found")
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
            if op == BooleanOpType.UNION:
                result = agent.csg.union(meshes[0], meshes[1])
            elif op == BooleanOpType.INTERSECTION:
                result = agent.csg.intersection(meshes[0], meshes[1])
            else:
                result = agent.csg.subtraction(meshes[0], meshes[1])
            resolved = agent.resolver.resolve(result)
            return resolved.mesh

        mesh = await loop.run_in_executor(None, _run)
        return MeshData.from_trimesh(mesh)
