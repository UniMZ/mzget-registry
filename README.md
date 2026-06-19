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

Import a PRIDE project manifest produced by MzGet:

```bash
mzget manifest PXD000001 --output /tmp/PXD000001.json
python3 tools/import_pride_manifest.py /tmp/PXD000001.json
python3 tools/build_registry.py
```
