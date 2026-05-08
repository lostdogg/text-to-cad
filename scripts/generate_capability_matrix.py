#!/usr/bin/env python3
"""Generate CAPABILITIES.md from code-level feature flags."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "CAPABILITIES.md"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.features import capability_matrix
from backend.app.metadata import APP_LICENSE, APP_VERSION


def main() -> int:
    rows = capability_matrix()
    lines = [
        "# Capability Matrix",
        "",
        f"Generated from code-level feature flags. Version: `{APP_VERSION}` · License: `{APP_LICENSE}`",
        "",
        "| Feature Flag | Enabled | Surface | Area | Description |",
        "|---|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {feature_flag} | {enabled} | {surface} | {area} | {description} |".format(
                feature_flag=row["feature_flag"],
                enabled="✅" if row["enabled"] else "❌",
                surface=row["surface"],
                area=row["area"],
                description=row["description"],
            )
        )

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
