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
  --state verified
python3 tools/build_registry.py
```

Promotion moves reviewed observation files from `data/observations/pending/` to `data/observations/reviewed/` by default, so `report_observations.py` only lists observations still awaiting review. Use `--keep-pending` only when debugging a promotion locally.

To promote a checksum to `verified`, use a quorum of independent submitters. The quorum count is based on distinct `submitter` values in matching pending observations:

```bash
python3 tools/promote_observation.py \
  data/observations/pending/pride/PXD000/PXD000001/<file_accession>/<observation>.json \
  --state verified \
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

File records may include inline checksum variants. Variants can store whole-file SHA-256/BLAKE3 values plus BLAKE3 block hashes, `block_size`, and `merkle_root`. MzGet clients treat `verified` variants as accepted verification inputs. Official and community labels are stored as checksum sources, not variant states. `conflict` variants are published as candidate checksums: clients may accept a download that matches one conflict candidate, upload that observation to help resolve the conflict, and add a new conflict candidate only after repeated local downloads agree.

Pending observations are stored under `data/observations/pending/` and published read-only by Pages. Reviewed observations are archived under `data/observations/reviewed/` and referenced by file variants. Current states are `none`, `verified`, and `conflict`: no variant means `none`; one accepted checksum is `verified`; disagreeing checksums are `conflict` until a later independent observation matches one side.

Validation rejects multiple current `verified` variants for the same file. A pending observation that disagrees with an existing `verified` variant must be explicitly marked `conflict`.
