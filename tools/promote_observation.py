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


def observation_key(observation: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        observation["source"],
        observation["dataset_accession"],
        observation["file_accession"],
        observation["sha256"].lower(),
    )


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


def reviewed_observation_path(path: Path) -> Path:
    pending = DATA / "observations" / "pending"
    reviewed = DATA / "observations" / "reviewed"
    try:
        relative = path.resolve().relative_to(pending.resolve())
    except ValueError:
        return path
    return reviewed / relative


def archive_observations(paths: list[Path]) -> list[Path]:
    archived = []
    for path in paths:
        target = reviewed_observation_path(path)
        if target == path:
            archived.append(path)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != path.read_bytes():
                raise SystemExit(
                    f"reviewed observation already exists with different content: {target}"
                )
            path.unlink()
        else:
            path.rename(target)
        archived.append(target)
    return archived


def build_variant(observation: dict[str, Any], state: str, refs: list[str]) -> dict[str, Any]:
    variant = {
        "sha256": observation["sha256"].lower(),
        "blake3": lower_or_none(observation.get("blake3")),
        "block_size": observation.get("block_size"),
        "merkle_root": lower_or_none(observation.get("merkle_root")),
        "verification_state": state,
        "observations": refs,
    }
    return {key: value for key, value in variant.items() if value is not None}


def lower_or_none(value: Any) -> Any:
    if isinstance(value, str):
        return value.lower()
    return value


def matching_pending_observations(
    observation: dict[str, Any]
) -> list[tuple[Path, dict[str, Any]]]:
    pending = DATA / "observations" / "pending"
    if not pending.exists():
        return []

    key = observation_key(observation)
    matches = []
    for candidate_path in sorted(pending.rglob("*.json")):
        candidate = read_json(candidate_path)
        if observation_key(candidate) == key:
            matches.append((candidate_path, candidate))
    return matches


def independent_submitters(entries: list[tuple[Path, dict[str, Any]]]) -> list[str]:
    return sorted(
        {
            observation.get("submitter")
            for _, observation in entries
            if observation.get("submitter")
        }
    )


def quorum_paths(observation: dict[str, Any], quorum: int) -> list[Path]:
    if quorum < 1:
        raise SystemExit("quorum must be greater than zero")

    matches = matching_pending_observations(observation)
    submitters = independent_submitters(matches)
    if len(submitters) < quorum:
        raise SystemExit(
            "community_verified requires at least "
            f"{quorum} independent submitter(s); found {len(submitters)}"
        )
    return [path for path, _ in matches]


def promote_observation(
    path: Path, state: str, update_existing: bool, quorum: int, keep_pending: bool
) -> None:
    if state not in PROMOTABLE_STATES:
        raise SystemExit(f"state must be one of {sorted(PROMOTABLE_STATES)}")

    observation = read_json(path)
    file_path = find_file_record(observation)
    record = read_json(file_path)
    variants = record.setdefault("variants", [])
    observation_paths = (
        quorum_paths(observation, quorum)
        if state == "community_verified"
        else [path]
    )
    ref_paths = observation_paths if keep_pending else archive_observations(observation_paths)
    refs = [observation_ref(path) for path in ref_paths]
    sha256 = observation["sha256"].lower()

    for variant in variants:
        if variant.get("sha256", "").lower() == sha256:
            observations = variant.setdefault("observations", [])
            for ref in refs:
                if ref not in observations:
                    observations.append(ref)
            if update_existing:
                variant["verification_state"] = state
            write_json(file_path, record)
            print(f"updated {file_path.relative_to(ROOT)}")
            return

    variants.append(build_variant(observation, state, refs))
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
    parser.add_argument(
        "--quorum",
        type=int,
        default=2,
        help="minimum independent submitters required for community_verified",
    )
    parser.add_argument(
        "--keep-pending",
        action="store_true",
        help="leave promoted observations under data/observations/pending",
    )
    args = parser.parse_args()
    promote_observation(
        args.observation,
        args.state,
        args.update_existing,
        args.quorum,
        args.keep_pending,
    )


if __name__ == "__main__":
    main()
