#!/usr/bin/env python3
"""Build static MzGet Registry Pages output from canonical data records."""

from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = Path(os.environ.get("MZGET_REGISTRY_OUT", str(ROOT / "public")))
BASE_URL = "https://registry.mzget.unimz.org"
VARIANT_STATES = {
    "official",
    "community_verified",
    "candidate",
    "conflict_candidate",
    "superseded",
    "historical",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_json_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*.json"):
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def accession_bucket(accession: str) -> str:
    if len(accession) >= 6:
        return accession[:6]
    return accession


def load_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    datasets = [read_json(path) for path in sorted((DATA / "datasets").rglob("*.json"))]
    files = [read_json(path) for path in sorted((DATA / "files").rglob("*.json"))]
    observations = [read_json(path) for path in sorted((DATA / "observations").rglob("*.json"))]
    return datasets, files, observations


def validate_records(
    datasets: list[dict[str, Any]], files: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> None:
    file_keys = {
        (record["source"], record["dataset_accession"], record["file_accession"])
        for record in files
    }
    for dataset in datasets:
        required = ["schema_version", "source", "accession", "file_count", "files"]
        missing = [key for key in required if key not in dataset]
        if missing:
            raise SystemExit(f"dataset {dataset.get('accession')} missing {missing}")
        if dataset["file_count"] != len(dataset["files"]):
            raise SystemExit(f"dataset {dataset['accession']} has inconsistent file_count")
        for ref in dataset["files"]:
            record = read_json(DATA / ref)
            key = (record["source"], record["dataset_accession"], record["file_accession"])
            if key not in file_keys:
                raise SystemExit(f"dataset {dataset['accession']} references missing file {ref}")

    for record in files:
        required = [
            "schema_version",
            "source",
            "dataset_accession",
            "file_accession",
            "file_name",
            "public_locations",
        ]
        missing = [key for key in required if key not in record]
        if missing:
            raise SystemExit(f"file {record.get('file_accession')} missing {missing}")
        validate_variants(record)

    for observation in observations:
        validate_observation(observation, file_keys)


def validate_observation(
    observation: dict[str, Any], file_keys: set[tuple[str, str, str]]
) -> None:
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

    key = (
        observation["source"],
        observation["dataset_accession"],
        observation["file_accession"],
    )
    if key not in file_keys:
        raise SystemExit(f"observation references missing file {key}")
    if not isinstance(observation["observed_at_unix_seconds"], int):
        raise SystemExit(f"observation for {key} has invalid observed_at_unix_seconds")
    if not is_hex_digest(observation.get("sha256"), 64):
        raise SystemExit(f"observation for {key} has invalid sha256")
    blake3 = observation.get("blake3")
    if blake3 is not None and not is_hex_digest(blake3, 64):
        raise SystemExit(f"observation for {key} has invalid blake3")


def validate_variants(record: dict[str, Any]) -> None:
    variants = record.get("variants", [])
    if not isinstance(variants, list):
        raise SystemExit(f"file {record.get('file_accession')} has non-array variants")

    for index, variant in enumerate(variants):
        if not isinstance(variant, dict):
            raise SystemExit(
                f"file {record.get('file_accession')} variant {index} is not an object"
            )
        state = variant.get("verification_state")
        if state not in VARIANT_STATES:
            raise SystemExit(
                f"file {record.get('file_accession')} variant {index} has invalid verification_state {state!r}"
            )
        if not is_hex_digest(variant.get("sha256"), 64):
            raise SystemExit(
                f"file {record.get('file_accession')} variant {index} has invalid sha256"
            )
        for key in ["blake3", "merkle_root"]:
            value = variant.get(key)
            if value is not None and not is_hex_digest(value, 64):
                raise SystemExit(
                    f"file {record.get('file_accession')} variant {index} has invalid {key}"
                )
        block_size = variant.get("block_size")
        if block_size is not None and (not isinstance(block_size, int) or block_size <= 0):
            raise SystemExit(
                f"file {record.get('file_accession')} variant {index} has invalid block_size"
            )


def is_hex_digest(value: Any, size: int) -> bool:
    return isinstance(value, str) and len(value) == size and all(
        char in "0123456789abcdefABCDEF" for char in value
    )


def registry_timestamp(datasets: list[dict[str, Any]]) -> int:
    values = [
        dataset.get("source_retrieved_at_unix_seconds")
        for dataset in datasets
        if isinstance(dataset.get("source_retrieved_at_unix_seconds"), int)
    ]
    return max(values) if values else 0



def prepare_output() -> None:
    if OUTPUT.resolve() == ROOT.resolve():
        raise SystemExit("refusing to use repository root as build output")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)



def variant_count(files: list[dict[str, Any]]) -> int:
    return sum(len(record.get("variants", [])) for record in files)


def build_html(
    datasets: list[dict[str, Any]],
    files: list[dict[str, Any]],
    variants: int,
    observations: int,
    generated_at: int,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MzGet Registry</title>
  <style>
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; color: #182026; background: #f7f8fa; }}
    header, main {{ max-width: 920px; margin: 0 auto; padding: 24px; }}
    header {{ padding-top: 36px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 650; letter-spacing: 0; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    p {{ margin: 0 0 14px; color: #4f5b66; line-height: 1.5; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric {{ border: 1px solid #d9dee4; background: #fff; border-radius: 8px; padding: 14px 16px; }}
    .metric span {{ display: block; color: #6b7680; font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    pre {{ overflow-x: auto; background: #fff; border: 1px solid #d9dee4; border-radius: 8px; padding: 14px 16px; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }}
    a {{ color: #0b5cad; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <header>
    <h1>MzGet Registry</h1>
    <p>Static integrity metadata for public mass spectrometry datasets.</p>
  </header>
  <main>
    <section class="metrics" aria-label="Registry metrics">
      <div class="metric"><span>Datasets</span><strong>{len(datasets)}</strong></div>
      <div class="metric"><span>Files</span><strong>{len(files)}</strong></div>
      <div class="metric"><span>Variants</span><strong>{variants}</strong></div>
      <div class="metric"><span>Observations</span><strong>{observations}</strong></div>
      <div class="metric"><span>Generated</span><strong>{generated_at}</strong></div>
    </section>
    <h2>Direct Lookup</h2>
    <p>MzGet clients compute dataset metadata URLs directly from the accession. No global dataset index is required for normal downloads.</p>
    <pre><code>https://registry.mzget.unimz.org/datasets/pride/PXD000/PXD000001.json</code></pre>
    <p>The bucket is the first six accession characters, for example <code>PXD000</code> for <code>PXD000001</code>.</p>
    <p>Registry metadata: <a href="latest.json"><code>latest.json</code></a>.</p>
  </main>
</body>
</html>
"""


def main() -> None:
    datasets, files, observations = load_records()
    validate_records(datasets, files, observations)
    prepare_output()
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")
    copy_json_tree(DATA / "datasets", OUTPUT / "datasets")
    copy_json_tree(DATA / "files", OUTPUT / "files")
    copy_json_tree(DATA / "observations", OUTPUT / "observations")
    copy_json_tree(ROOT / "schema", OUTPUT / "schema")

    generated_at = registry_timestamp(datasets)
    variants = variant_count(files)
    latest = {
        "schema_version": 1,
        "name": "MzGet Registry",
        "base_url": BASE_URL,
        "generated_at_unix_seconds": generated_at,
        "counts": {
            "datasets": len(datasets),
            "files": len(files),
            "variants": variants,
            "observations": len(observations),
        },
        "dataset_lookup": {
            "template": "datasets/{source_lower}/{bucket}/{accession}.json",
            "bucket_rule": "first six accession characters, e.g. PXD000 for PXD000001"
        },
    }
    write_json(OUTPUT / "latest.json", latest)
    (OUTPUT / "index.html").write_text(
        build_html(datasets, files, variants, len(observations), generated_at), encoding="utf-8"
    )
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy2(cname, OUTPUT / "CNAME")


if __name__ == "__main__":
    main()
