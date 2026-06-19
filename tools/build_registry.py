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


def load_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    datasets = [read_json(path) for path in sorted((DATA / "datasets").rglob("*.json"))]
    files = [read_json(path) for path in sorted((DATA / "files").rglob("*.json"))]
    return datasets, files


def validate_records(datasets: list[dict[str, Any]], files: list[dict[str, Any]]) -> None:
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


def build_html(datasets: list[dict[str, Any]], files: list[dict[str, Any]], generated_at: int) -> str:
    rows = []
    for dataset in datasets:
        dataset_path = f"datasets/{dataset['source'].lower()}/{accession_bucket(dataset['accession'])}/{dataset['accession']}.json"
        rows.append(
            "<tr>"
            f"<td>{html.escape(dataset['source'])}</td>"
            f"<td><a href=\"{dataset_path}\">{html.escape(dataset['accession'])}</a></td>"
            f"<td>{dataset['file_count']}</td>"
            f"<td>{dataset.get('total_size_bytes', 0)}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MzGet Registry</title>
  <style>
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; color: #182026; background: #f7f8fa; }}
    header, main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    header {{ padding-top: 36px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 650; letter-spacing: 0; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    p {{ margin: 0; color: #4f5b66; line-height: 1.5; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric {{ border: 1px solid #d9dee4; background: #fff; border-radius: 8px; padding: 14px 16px; }}
    .metric span {{ display: block; color: #6b7680; font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9dee4; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e7eaee; text-align: left; font-size: 14px; }}
    th {{ color: #4f5b66; background: #eef1f4; font-weight: 600; }}
    a {{ color: #0b5cad; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{ background: #eef1f4; border-radius: 4px; padding: 2px 5px; }}
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
      <div class="metric"><span>Generated</span><strong>{generated_at}</strong></div>
    </section>
    <p>Machine-readable entry points: <a href="latest.json"><code>latest.json</code></a>, <a href="index.json"><code>index.json</code></a>, per-dataset JSON files, and <a href="snapshots/registry.json"><code>registry.json</code></a>.</p>
    <h2>Datasets</h2>
    <table>
      <thead><tr><th>Source</th><th>Accession</th><th>Files</th><th>Repository Size Bytes</th></tr></thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def main() -> None:
    datasets, files = load_records()
    validate_records(datasets, files)
    prepare_output()
    copy_json_tree(DATA / "datasets", OUTPUT / "datasets")
    copy_json_tree(DATA / "files", OUTPUT / "files")
    copy_json_tree(ROOT / "schema", OUTPUT / "schema")

    generated_at = registry_timestamp(datasets)
    snapshot = {
        "schema_version": 1,
        "name": "MzGet Registry",
        "base_url": BASE_URL,
        "generated_at_unix_seconds": generated_at,
        "counts": {"datasets": len(datasets), "files": len(files), "variants": 0},
        "datasets": datasets,
        "files": files,
    }
    write_json(OUTPUT / "snapshots" / "registry.json", snapshot)
    latest = {
        "schema_version": 1,
        "name": "MzGet Registry",
        "base_url": BASE_URL,
        "generated_at_unix_seconds": generated_at,
        "counts": snapshot["counts"],
        "snapshots": {"json": "snapshots/registry.json"},
        "index": "index.json",
    }
    write_json(OUTPUT / "latest.json", latest)
    write_json(
        OUTPUT / "index.json",
        {
            "schema_version": 1,
            "base_url": BASE_URL,
            "generated_at_unix_seconds": generated_at,
            "datasets": [
                {
                    "source": dataset["source"],
                    "accession": dataset["accession"],
                    "file_count": dataset["file_count"],
                    "total_size_bytes": dataset.get("total_size_bytes", 0),
                    "path": f"datasets/{dataset['source'].lower()}/{accession_bucket(dataset['accession'])}/{dataset['accession']}.json",
                }
                for dataset in datasets
            ],
        },
    )
    (OUTPUT / "index.html").write_text(build_html(datasets, files, generated_at), encoding="utf-8")
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy2(cname, OUTPUT / "CNAME")


if __name__ == "__main__":
    main()
