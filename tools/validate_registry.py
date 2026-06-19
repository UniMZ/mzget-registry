#!/usr/bin/env python3
"""Validate MzGet Registry source records and generated Pages output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json_tree(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for file in sorted(path.rglob("*.json")):
        read_json(file)
        count += 1
    return count


def run_build(output: Path) -> None:
    env = os.environ.copy()
    env["MZGET_REGISTRY_OUT"] = str(output)
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_registry.py")],
        cwd=ROOT,
        env=env,
        check=True,
    )


def validate_pages_output(output: Path) -> None:
    latest = read_json(output / "latest.json")
    counts = latest.get("counts", {})
    for key in ["datasets", "files", "variants", "observations"]:
        if not isinstance(counts.get(key), int):
            raise SystemExit(f"latest.json missing integer counts.{key}")

    required = [
        output / ".nojekyll",
        output / "schema" / "dataset.schema.json",
        output / "schema" / "file.schema.json",
        output / "schema" / "variant.schema.json",
        output / "schema" / "observation.schema.json",
    ]
    for path in required:
        if not path.exists():
            raise SystemExit(f"generated output missing {path.relative_to(output)}")

    validate_json_tree(output)


def main() -> None:
    schema_count = validate_json_tree(ROOT / "schema")
    data_count = validate_json_tree(ROOT / "data")

    with tempfile.TemporaryDirectory(prefix="mzget-registry-") as tmp:
        output = Path(tmp) / "public"
        run_build(output)
        validate_pages_output(output)

    print(f"validated {schema_count} schema JSON file(s) and {data_count} data JSON file(s)")


if __name__ == "__main__":
    main()
