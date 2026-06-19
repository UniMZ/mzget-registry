#!/usr/bin/env python3
"""Import a MzGet PRIDE source manifest into canonical registry records."""

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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    source = manifest["source"].lower()
    accession = manifest["accession"]
    bucket = accession_bucket(accession)
    file_refs: list[str] = []
    total_size = 0

    for source_file in manifest.get("files", []):
        file_accession = source_file["file_accession"]
        file_path = Path("files") / source / bucket / accession / f"{file_accession}.json"
        file_refs.append(str(file_path).replace("\\", "/"))
        size = source_file.get("file_size_bytes")
        if isinstance(size, int):
            total_size += size
        checksum = source_file.get("checksum")
        record = {
            "schema_version": 1,
            "source": manifest["source"],
            "dataset_accession": accession,
            "file_accession": file_accession,
            "file_name": source_file["file_name"],
            "category": source_file.get("category"),
            "category_name": source_file.get("category_name"),
            "repository_size_bytes": size,
            "repository_size_kind": "repository_reported",
            "checksum": checksum,
            "checksum_source": "official" if checksum else None,
            "public_locations": source_file.get("public_locations", []),
            "preferred_download_url": source_file.get("preferred_download_url"),
            "submission_date": source_file.get("submission_date"),
            "publication_date": source_file.get("publication_date"),
            "updated_date": source_file.get("updated_date"),
            "variants": [],
        }
        write_json(DATA / file_path, record)

    dataset = {
        "schema_version": 1,
        "source": manifest["source"],
        "accession": accession,
        "source_retrieved_at_unix_seconds": manifest.get("retrieved_at_unix_seconds"),
        "file_count": len(file_refs),
        "total_size_bytes": total_size,
        "files": file_refs,
    }
    write_json(DATA / "datasets" / source / bucket / f"{accession}.json", dataset)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    import_manifest(args.manifest)


if __name__ == "__main__":
    main()
