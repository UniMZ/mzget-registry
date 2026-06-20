#!/usr/bin/env python3
"""Report pending observation groups for registry review."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STRICT_VARIANT_STATES = {"official", "community_verified"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_file_records() -> dict[tuple[str, str, str], dict[str, Any]]:
    records = {}
    for path in sorted((DATA / "files").rglob("*.json")):
        record = read_json(path)
        key = (record["source"], record["dataset_accession"], record["file_accession"])
        records[key] = record
    return records


def load_pending_observations() -> list[tuple[Path, dict[str, Any]]]:
    root = DATA / "observations" / "pending"
    if not root.exists():
        return []
    return [(path, read_json(path)) for path in sorted(root.rglob("*.json"))]


def trusted_sha256s(record: dict[str, Any]) -> set[str]:
    return {
        variant["sha256"].lower()
        for variant in record.get("variants", [])
        if variant.get("verification_state") in STRICT_VARIANT_STATES
    }


def observation_report(quorum: int) -> dict[str, Any]:
    files = load_file_records()
    observations = load_pending_observations()
    groups: dict[tuple[str, str, str, str], list[tuple[Path, dict[str, Any]]]] = defaultdict(list)

    for path, observation in observations:
        key = (
            observation["source"],
            observation["dataset_accession"],
            observation["file_accession"],
            observation["sha256"].lower(),
        )
        groups[key].append((path, observation))

    group_reports = []
    for (source, dataset, file_accession, sha256), entries in sorted(groups.items()):
        file_key = (source, dataset, file_accession)
        file_record = files.get(file_key, {})
        trusted = trusted_sha256s(file_record)
        if trusted and sha256 in trusted:
            recommendation = "matches_trusted"
        elif trusted:
            recommendation = "conflict_candidate"
        elif len(entries) >= quorum:
            recommendation = "quorum_candidate"
        else:
            recommendation = "candidate"

        observed_times = [
            observation.get("observed_at_unix_seconds")
            for _, observation in entries
            if isinstance(observation.get("observed_at_unix_seconds"), int)
        ]
        submitters = sorted(
            {
                observation.get("submitter")
                for _, observation in entries
                if observation.get("submitter")
            }
        )
        group_reports.append(
            {
                "source": source,
                "dataset_accession": dataset,
                "file_accession": file_accession,
                "file_name": file_record.get("file_name"),
                "sha256": sha256,
                "observations": len(entries),
                "submitters": submitters,
                "first_observed_at_unix_seconds": min(observed_times) if observed_times else None,
                "last_observed_at_unix_seconds": max(observed_times) if observed_times else None,
                "trusted_sha256s": sorted(trusted),
                "recommendation": recommendation,
                "observation_files": [
                    str(path.relative_to(ROOT)).replace("\\", "/") for path, _ in entries
                ],
            }
        )

    return {
        "schema_version": 1,
        "quorum": quorum,
        "pending_observations": len(observations),
        "groups": group_reports,
    }


def print_text(report: dict[str, Any]) -> None:
    print(
        f"pending_observations={report['pending_observations']} groups={len(report['groups'])} quorum={report['quorum']}"
    )
    for group in report["groups"]:
        print(
            "\t".join(
                [
                    group["recommendation"],
                    group["source"],
                    group["dataset_accession"],
                    group["file_accession"],
                    str(group["observations"]),
                    group["sha256"],
                    group.get("file_name") or "-",
                ]
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quorum", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.quorum < 1:
        raise SystemExit("quorum must be greater than zero")

    report = observation_report(args.quorum)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)


if __name__ == "__main__":
    main()
