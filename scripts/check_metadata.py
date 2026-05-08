#!/usr/bin/env python3
"""Validate version/legal metadata consistency across project files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "version.json"
FRONTEND_PACKAGE = ROOT / "frontend" / "package.json"
LICENSE_FILE = ROOT / "LICENSE"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    metadata = load_json(VERSION_FILE)
    package = load_json(FRONTEND_PACKAGE)
    license_text = LICENSE_FILE.read_text(encoding="utf-8")

    required = ("name", "version", "license", "copyright")
    missing = [k for k in required if not metadata.get(k)]
    if missing:
        print(f"ERROR: missing required fields in version.json: {missing}")
        return 1

    if package.get("version") != metadata["version"]:
        print(
            "ERROR: frontend/package.json version mismatch. "
            f"package.json={package.get('version')} version.json={metadata['version']}"
        )
        return 1

    if metadata["license"] != "MIT":
        print(f"ERROR: unexpected license in version.json: {metadata['license']}")
        return 1

    if "MIT License" not in license_text:
        print("ERROR: LICENSE file missing MIT header")
        return 1

    if not re.search(r"Copyright \(c\)\s+\d{4}", license_text):
        print("ERROR: LICENSE file missing copyright statement")
        return 1

    print("Metadata check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
