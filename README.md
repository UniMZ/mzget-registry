# MzGet Registry

Community integrity registry for reliable downloads of public mass spectrometry datasets.

This repository is managed by `mzget-registry-server` on `main`, with GitHub Pages configured to publish from the repository root. The JSON records under `datasets/`, `files/`, and `observations/` are both the canonical registry data and the public static query paths. There is no duplicated `data/` tree, no GitHub Actions build step, and no maintenance script in this repository.

Public endpoint:

```text
https://registry.mzget.unimz.org
```

## Layout

- `datasets/`: canonical dataset records and public query paths.
- `files/`: canonical file records and public query paths.
- `observations/`: accepted user checksum observations and public evidence records.
- `schema/`: JSON schema files.
- `latest.json`: generated registry metadata.
- `index.html`: generated human-readable registry page.
- `CNAME`: GitHub Pages custom domain.

The normal client lookup path does not require a global dataset index. For example, `PXD000001` is addressed directly:

```text
https://registry.mzget.unimz.org/datasets/pride/PXD000/PXD000001.json
```

The bucket is the first six accession characters, for example `PXD000` for `PXD000001`.

## Management

The standard write path is:

1. `mzget` downloads and verifies user files.
2. `mzget` submits observations to the management API.
3. `mzget-registry-server serve` validates the observations.
4. The server updates `datasets/`, `files/`, and `observations/`, resolves registry state, regenerates `latest.json` and `index.html`, commits the result, and pushes `main`.
5. GitHub Pages serves `main` directly from the repository root.

The server checkout must be a clean checkout of `main` with a push-capable `origin` remote.

```bash
mzget-registry-server serve \
  --registry-dir /srv/mzget-registry \
  --bind 127.0.0.1:8787 \
  --publish-remote origin \
  --publish-branch main
```

Local administrator commands are provided by the same server binary:

```bash
mzget-registry-server validate --registry-dir /path/to/mzget-registry
mzget-registry-server build --registry-dir /path/to/mzget-registry
mzget-registry-server import-manifest --registry-dir /path/to/mzget-registry /tmp/PXD000001.json
```

## Registry State

File records may include checksum variants with whole-file SHA-256/BLAKE3 values, BLAKE3 block hashes, `block_size`, and `merkle_root`.

Current states are:

- `none`: no variant is available.
- `verified`: one checksum is currently accepted.
- `conflict`: multiple checksums are observed for the same file identity.

Official and community labels are stored as checksum sources, not as states. Validation rejects multiple current `verified` variants for the same file.
