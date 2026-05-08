"""Canonical application metadata loaded from repository root version.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_FILE = REPO_ROOT / "version.json"


def load_metadata() -> Dict[str, Any]:
    with METADATA_FILE.open("r", encoding="utf-8") as fh:
        metadata = json.load(fh)
    required = ("name", "version", "license", "copyright")
    missing = [k for k in required if not metadata.get(k)]
    if missing:
        raise ValueError(f"Missing required metadata fields in {METADATA_FILE}: {missing}")
    return metadata


APP_METADATA = load_metadata()
APP_NAME: str = APP_METADATA["name"]
APP_VERSION: str = APP_METADATA["version"]
APP_LICENSE: str = APP_METADATA["license"]
