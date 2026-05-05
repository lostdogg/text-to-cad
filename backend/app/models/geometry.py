"""Pydantic models for geometry and CAD data structures."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Vector3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]

    @classmethod
    def from_list(cls, data: List[float]) -> "Vector3":
        return cls(x=data[0], y=data[1], z=data[2])


class Transform(BaseModel):
    position: Vector3 = Field(default_factory=Vector3)
    rotation: Vector3 = Field(default_factory=Vector3)  # Euler angles in degrees
    scale: Vector3 = Field(default_factory=lambda: Vector3(x=1.0, y=1.0, z=1.0))


class PrimitiveType(str, Enum):
    BOX = "box"
    CYLINDER = "cylinder"
    SPHERE = "sphere"
    CONE = "cone"
    TORUS = "torus"


class PrimitiveSpec(BaseModel):
    """Specification for a primitive geometry shape."""

    model_config = ConfigDict(use_enum_values=True)

    type: PrimitiveType
    dimensions: Dict[str, float] = Field(default_factory=dict)
    transform: Transform = Field(default_factory=Transform)
    name: Optional[str] = None


class BooleanOpType(str, Enum):
    UNION = "union"
    INTERSECTION = "intersection"
    SUBTRACTION = "subtraction"


class BooleanOpSpec(BaseModel):
    """Specification for a boolean (CSG) operation between two geometry specs."""

    model_config = ConfigDict(use_enum_values=True)

    operation: BooleanOpType
    # Each operand can be a primitive index (int) or another BooleanOpSpec
    operand_a: Any  # int index or nested BooleanOpSpec
    operand_b: Any  # int index or nested BooleanOpSpec
    name: Optional[str] = None


class GeometrySpec(BaseModel):
    """Complete geometry specification produced by NLP parsing."""

    primitives: List[PrimitiveSpec] = Field(default_factory=list)
    operations: List[BooleanOpSpec] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""

    def has_operations(self) -> bool:
        return len(self.operations) > 0


class MeshData(BaseModel):
    """Serialisable mesh representation (JSON-safe lists)."""

    vertices: List[List[float]] = Field(default_factory=list)
    faces: List[List[int]] = Field(default_factory=list)
    normals: List[List[float]] = Field(default_factory=list)
    vertex_count: int = 0
    face_count: int = 0

    @classmethod
    def from_trimesh(cls, mesh: Any) -> "MeshData":
        """Convert a trimesh.Trimesh to MeshData."""
        import numpy as np

        vertices = mesh.vertices.tolist()
        faces = mesh.faces.tolist()
        if mesh.vertex_normals is not None and len(mesh.vertex_normals) > 0:
            normals = mesh.vertex_normals.tolist()
        else:
            normals = []
        return cls(
            vertices=vertices,
            faces=faces,
            normals=normals,
            vertex_count=len(vertices),
            face_count=len(faces),
        )

    def to_trimesh(self) -> Any:
        """Convert MeshData back to a trimesh.Trimesh."""
        import numpy as np
        import trimesh

        vertices = np.array(self.vertices, dtype=np.float64)
        faces = np.array(self.faces, dtype=np.int64)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        return mesh


class CADModel(BaseModel):
    """A complete CAD model with geometry spec, mesh data, and metadata."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Model"
    description: str = ""
    geometry_spec: Optional[GeometrySpec] = None
    mesh_data: Optional[MeshData] = None
    source_text: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
