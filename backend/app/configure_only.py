"""Container configure-only entrypoint."""

from __future__ import annotations

from typing import List

from .config import settings
from .metadata import APP_VERSION


def validate_configuration() -> List[str]:
    errors: List[str] = []
    if not settings.HOST:
        errors.append("HOST must not be empty")
    if not isinstance(settings.PORT, int) or settings.PORT <= 0:
        errors.append("PORT must be a positive integer")
    if not settings.EXPORT_DIR:
        errors.append("EXPORT_DIR must not be empty")
    if settings.MODE not in {"local", "cloud"}:
        errors.append("MODE must be either 'local' or 'cloud'")
    return errors


def main() -> int:
    errors = validate_configuration()
    if errors:
        print(f"[configure-only] text-to-cad v{APP_VERSION} configuration invalid:")
        for e in errors:
            print(f"- {e}")
        return 1

    print(f"[configure-only] text-to-cad v{APP_VERSION} configuration valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
