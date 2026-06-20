#!/usr/bin/env python3
"""Lightweight tests for MzGet Registry review tools."""

from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import promote_observation
import report_observations

SHA256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
BLAKE3 = "ea8f163db38682925e4491c5e58d4bb3506a940bcbbf6f14e45344b721d16c27"
BLOCK_1 = "6d227a88f75cd8f49286c6140cd03996bf5f32b703a356a1de160823c8369ee4"
BLOCK_2 = "0891763fa8a55f4a4c6cae9a6a79fd9d7d0f3fa2fea0ec9a8efda9c385f1517a"


def configure_tools(root: Path) -> None:
    promote_observation.ROOT = root
    promote_observation.DATA = root / "data"
    report_observations.ROOT = root
    report_observations.DATA = root / "data"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_file_record(root: Path) -> Path:
    path = root / "data" / "files" / "pride" / "PXD000" / "PXD000001" / "file.raw.json"
    write_json(
        path,
        {
            "source": "PRIDE",
            "dataset_accession": "PXD000001",
            "file_accession": "file-1",
            "file_name": "file.raw",
            "variants": [],
        },
    )
    return path


def observation(submitter: str, observed_at: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "PRIDE",
        "dataset_accession": "PXD000001",
        "file_accession": "file-1",
        "file_name": "file.raw",
        "observed_at_unix_seconds": observed_at,
        "sha256": SHA256,
        "blake3": BLAKE3,
        "file_size_bytes": 5,
        "block_size": 4,
        "block_hash_algorithm": "blake3",
        "blocks": [BLOCK_1.upper(), BLOCK_2.upper()],
        "merkle_root": BLAKE3,
        "verification_state": "local_observed",
        "path": "file.raw",
        "submitter": submitter,
        "tool": {"name": "MzGet", "version": "0.1.0"},
        "format_qc": {"status": "skipped", "format": None, "checks": []},
    }


def write_observation(root: Path, submitter: str, observed_at: int) -> Path:
    path = (
        root
        / "data"
        / "observations"
        / "pending"
        / "pride"
        / "PXD000"
        / "PXD000001"
        / "file-1"
        / f"{observed_at}-{SHA256[:16]}.json"
    )
    write_json(path, observation(submitter, observed_at))
    return path


def test_report_quorum_uses_distinct_submitters() -> None:
    with tempfile.TemporaryDirectory(prefix="mzget-registry-tools-") as tmp:
        root = Path(tmp)
        configure_tools(root)
        write_file_record(root)
        write_observation(root, "alice", 1)
        second = write_observation(root, "alice", 2)

        report = report_observations.observation_report(quorum=2)
        group = report["groups"][0]
        assert group["recommendation"] == "candidate"
        assert group["independent_submitters"] == 1

        write_json(second, observation("bob", 2))
        report = report_observations.observation_report(quorum=2)
        group = report["groups"][0]
        assert group["recommendation"] == "quorum_candidate"
        assert group["independent_submitters"] == 2


def test_promote_community_verified_enforces_quorum() -> None:
    with tempfile.TemporaryDirectory(prefix="mzget-registry-tools-") as tmp:
        root = Path(tmp)
        configure_tools(root)
        file_record = write_file_record(root)
        first = write_observation(root, "alice", 1)

        try:
            with redirect_stdout(StringIO()):
                promote_observation.promote_observation(
                    first,
                    "community_verified",
                    update_existing=False,
                    quorum=2,
                    keep_pending=False,
                )
        except SystemExit as error:
            assert "requires at least 2" in str(error)
        else:
            raise AssertionError("community_verified promotion passed without quorum")

        write_observation(root, "bob", 2)
        with redirect_stdout(StringIO()):
            promote_observation.promote_observation(
                first,
                "community_verified",
                update_existing=False,
                quorum=2,
                keep_pending=False,
            )

        record = read_json(file_record)
        assert len(record["variants"]) == 1
        variant = record["variants"][0]
        assert variant["verification_state"] == "community_verified"
        assert len(variant["observations"]) == 2
        assert variant["block_hash_algorithm"] == "blake3"
        assert variant["blocks"] == [BLOCK_1, BLOCK_2]
        assert all("/reviewed/" in observation for observation in variant["observations"])
        assert not first.exists()
        assert report_observations.observation_report(quorum=2)["pending_observations"] == 0


def main() -> None:
    test_report_quorum_uses_distinct_submitters()
    test_promote_community_verified_enforces_quorum()
    print("registry tool tests passed")


if __name__ == "__main__":
    main()
