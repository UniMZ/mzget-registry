# MzGet Registry

Community integrity registry for reliable downloads of public mass spectrometry datasets.

This repository stores machine-readable metadata for MzGet. The primary lookup path is per-dataset JSON: a client that needs `PXD000001` can fetch only `datasets/pride/PXD000/PXD000001.json`, then the referenced file records.

- dataset records under `data/datasets/`;
- file records under `data/files/`;
- JSON schemas under `schema/`;
- generated GitHub Pages output under `public/` locally and the `gh-pages` branch on GitHub.

The public registry endpoint is:

```text
https://registry.mzget.unimz.org
```

## Build

Generate the static registry and Pages files locally:

```bash
python3 tools/build_registry.py
```

The `public/` directory is generated and ignored on `main`. GitHub Actions publishes it to the `gh-pages` branch.

Validate source records and generated Pages output:

```bash
python3 tools/validate_registry.py
```

Import a PRIDE project manifest produced by MzGet:

```bash
mzget manifest PXD000001 --output /tmp/PXD000001.json
python3 tools/import_pride_manifest.py /tmp/PXD000001.json
python3 tools/build_registry.py
```

Import observation JSON produced by `mzget submit`:

```bash
mzget submit /path/to/mzget.lock.json --output /tmp/observations.json
python3 tools/import_observations.py /tmp/observations.json
python3 tools/build_registry.py
```

Or write pending observation files directly from a local registry checkout:

```bash
mzget submit /path/to/mzget.lock.json --registry-dir .
python3 tools/build_registry.py
```

After review, promote a pending observation into a checksum variant:

```bash
python3 tools/report_observations.py
python3 tools/promote_observation.py \
  data/observations/pending/pride/PXD000/PXD000001/<file_accession>/<observation>.json \
  --state candidate
python3 tools/build_registry.py
```

Promotion moves reviewed observation files from `data/observations/pending/` to `data/observations/reviewed/` by default, so `report_observations.py` only lists observations still awaiting review. Use `--keep-pending` only when debugging a promotion locally.

To promote a checksum to `community_verified`, use a quorum of independent submitters. The quorum count is based on distinct `submitter` values in matching pending observations:

```bash
python3 tools/promote_observation.py \
  data/observations/pending/pride/PXD000/PXD000001/<file_accession>/<observation>.json \
  --state community_verified \
  --quorum 2 \
  --update-existing
```

## Lookup Model

The registry does not require a global dataset index for normal downloads. A client that knows the accession can compute the dataset URL directly. For example, `PXD000001` is stored under the bucket `PXD000`:

```text
https://registry.mzget.unimz.org/datasets/pride/PXD000/PXD000001.json
```

The dataset record then lists the file records needed for verification and download planning. `latest.json` only advertises schema-level metadata and the deterministic path rule; it does not contain a global dataset list.

File records are named from the original repository file name with a `.json` suffix, for example `sample.raw.json`. If a dataset contains duplicate file names, the importer appends a short `file_accession` suffix to avoid collisions.

File records may include inline checksum variants. MzGet clients treat `official` and `community_verified` variants as strict verification inputs and ignore `candidate` or `conflict_candidate` variants for default acceptance.

Pending observations are stored under `data/observations/pending/` and published read-only by Pages. Reviewed observations are archived under `data/observations/reviewed/` and referenced by file variants. Promotion from observations to `community_verified` variants is intentionally a reviewed registry change, not a client-side automatic write. `community_verified` promotion requires the configured quorum of distinct submitters.

Validation rejects multiple current trusted variants (`official` or `community_verified`) for the same file. A pending observation that disagrees with an existing trusted variant must be explicitly marked `conflict_candidate`.
