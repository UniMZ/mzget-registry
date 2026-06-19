#!/usr/bin/env python3
"""Promote a pending observation into a reviewed file checksum variant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROMOTABLE_STATES = {"candidate", "community_verified", "conflict_candidate"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_file_record(observation: dict[str, Any]) -> Path:
    source = observation["source"]
    dataset_accession = observation["dataset_accession"]
    file_accession = observation["file_accession"]
    matches = []

    for path in (DATA / "files").rglob("*.json"):
        record = read_json(path)
        if (
            record.get("source") == source
            and record.get("dataset_accession") == dataset_accession
            and record.get("file_accession") == file_accession
        ):
            matches.append(path)

    if not matches:
        raise SystemExit(
            f"no file record found for {(source, dataset_accession, file_accession)}"
        )
    if len(matches) > 1:
        raise SystemExit(
            f"multiple file records found for {(source, dataset_accession, file_accession)}"
        )
    return matches[0]


def observation_ref(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def build_variant(observation: dict[str, Any], state: str, ref: str) -> dict[str, Any]:
    variant = {
        "sha256": observation["sha256"].lower(),
        "blake3": lower_or_none(observation.get("blake3")),
        "block_size": observation.get("block_size"),
        "merkle_root": lower_or_none(observation.get("merkle_root")),
        "verification_state": state,
        "observations": [ref],
    }
    return {key: value for key, value in variant.items() if value is not None}


def lower_or_none(value: Any) -> Any:
    if isinstance(value, str):
        return value.lower()
    return value


def promote_observation(path: Path, state: str, update_existing: bool) -> None:
    if state not in PROMOTABLE_STATES:
        raise SystemExit(f"state must be one of {sorted(PROMOTABLE_STATES)}")

    observation = read_json(path)
    file_path = find_file_record(observation)
    record = read_json(file_path)
    variants = record.setdefault("variants", [])
    ref = observation_ref(path)
    sha256 = observation["sha256"].lower()

    for variant in variants:
        if variant.get("sha256", "").lower() == sha256:
            observations = variant.setdefault("observations", [])
            if ref not in observations:
                observations.append(ref)
            if update_existing:
                variant["verification_state"] = state
            write_json(file_path, record)
            print(f"updated {file_path.relative_to(ROOT)}")
            return

    variants.append(build_variant(observation, state, ref))
    write_json(file_path, record)
    print(f"updated {file_path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("observation", type=Path)
    parser.add_argument(
        "--state",
        choices=sorted(PROMOTABLE_STATES),
        default="candidate",
        help="reviewed variant state to create",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="update verification_state when a variant with the same sha256 already exists",
    )
    args = parser.parse_args()
    promote_observation(args.observation, args.state, args.update_existing)


if __name__ == "__main__":
    main()
