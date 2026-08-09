#!/usr/bin/env python3
"""Exports the backend's OpenAPI schema to JSON, without needing a live
server or a database connection -- FastAPI's schema generation only
introspects routes and Pydantic models; SQLAlchemy's engine is lazy and
never actually connects during this.

Used by the frontend's `npm run generate:types` (openapi-typescript) to
keep frontend/src/types/api.generated.ts in sync with the backend's real
API contract instead of hand-maintained parallel type definitions -- see
frontend/README.md for the full two-step workflow.

Usage:
    python scripts/export_openapi.py [output_path]
    (default output_path: ../frontend/openapi.json)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.main import app  # noqa: E402

_DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "openapi.json")


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_OUT
    with open(out_path, "w") as f:
        json.dump(app.openapi(), f, indent=2)
    print(f"Wrote OpenAPI schema to {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
