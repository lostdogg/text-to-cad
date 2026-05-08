"""Code-level feature registry and capability matrix source of truth."""

from __future__ import annotations

from typing import Any, Dict, List


FEATURE_FLAGS: Dict[str, Dict[str, Any]] = {
    "text_to_cad_generation": {
        "enabled": True,
        "surface": "backend",
        "area": "solids",
        "description": "Natural language to solid CAD generation pipeline",
    },
    "wireframe_view": {
        "enabled": True,
        "surface": "frontend",
        "area": "wireframe",
        "description": "Wireframe visualization and toggle controls",
    },
    "cam_cnc_generation": {
        "enabled": True,
        "surface": "backend",
        "area": "cam",
        "description": "3-axis CNC G-code and cost/time estimation",
    },
    "cam_3dprint_generation": {
        "enabled": True,
        "surface": "backend",
        "area": "cam",
        "description": "3D print G-code and process optimization",
    },
    "cam_laser_generation": {
        "enabled": True,
        "surface": "backend",
        "area": "cam",
        "description": "Laser profile extraction and G-code generation",
    },
    "collaboration_setup_workflow": {
        "enabled": True,
        "surface": "frontend+backend",
        "area": "setup_workflow",
        "description": "Session setup, participant management, and chat workflow",
    },
}


def capability_matrix() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, item in FEATURE_FLAGS.items():
        rows.append(
            {
                "feature_flag": key,
                "enabled": bool(item.get("enabled", False)),
                "surface": item.get("surface", "unknown"),
                "area": item.get("area", "unknown"),
                "description": item.get("description", ""),
            }
        )
    return sorted(rows, key=lambda r: r["feature_flag"])
