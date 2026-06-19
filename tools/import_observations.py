#!/usr/bin/env python3
"""Import MzGet observation JSON into pending registry observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def accession_bucket(accession: str) -> str:
    if len(accession) >= 6:
        return accession[:6]
    return accession


def safe_segment(value: str) -> str:
    return value.replace("/", "_")


def read_observations(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        observations = data
    elif isinstance(data, dict) and isinstance(data.get("observations"), list):
        observations = data["observations"]
    elif isinstance(data, dict):
        observations = [data]
    else:
        raise SystemExit("observation input must be an object, an array, or an observations bundle")

    for observation in observations:
        if not isinstance(observation, dict):
            raise SystemExit("each observation must be an object")
    return observations


def validate_observation(observation: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "source",
        "dataset_accession",
        "file_accession",
        "observed_at_unix_seconds",
        "sha256",
    ]
    missing = [key for key in required if key not in observation]
    if missing:
        raise SystemExit(f"observation missing {missing}")
    if not is_hex_digest(observation["sha256"], 64):
        raise SystemExit("observation has invalid sha256")
    blake3 = observation.get("blake3")
    if blake3 is not None and not is_hex_digest(blake3, 64):
        raise SystemExit("observation has invalid blake3")


def is_hex_digest(value: Any, size: int) -> bool:
    return isinstance(value, str) and len(value) == size and all(
        char in "0123456789abcdefABCDEF" for char in value
    )


def observation_path(observation: dict[str, Any]) -> Path:
    source = observation["source"].lower()
    accession = observation["dataset_accession"]
    bucket = accession_bucket(accession)
    file_accession = safe_segment(observation["file_accession"])
    observed_at = observation["observed_at_unix_seconds"]
    sha256 = observation["sha256"].lower()
    name = f"{observed_at}-{sha256[:16]}.json"
    return (
        DATA
        / "observations"
        / "pending"
        / source
        / bucket
        / accession
        / file_accession
        / name
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_observations(path: Path) -> None:
    observations = read_observations(path)
    for observation in observations:
        validate_observation(observation)
        target = observation_path(observation)
        write_json(target, observation)
        print(f"wrote {target.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    import_observations(args.observations)


if __name__ == "__main__":
    main()
