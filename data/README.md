# data/

Local, **untracked** data lake. Nothing under `raw/`, `interim/` or `processed/`
is committed (see `.gitignore`). `python scripts/check_repo_hygiene.py` fails if
geospatial files or large files are ever tracked.

| Directory | Contents | Rules |
|---|---|---|
| `raw/` | Datasets exactly as acquired + `manifest.json` (URL/endpoint, timestamps, size, SHA-256, licence, publisher metadata) | Never edited or overwritten. One sub-directory per registry id: `raw/<source_id>/<version-or-date>/`. Record the acquisition in `docs/research/data-source-registry.yaml`. See [data-lifecycle.md](../docs/architecture/data-lifecycle.md). |
| `interim/` | Cleaned/reprojected intermediates | Reproducible from `raw/` + code. Safe to delete. |
| `processed/` | Analysis-ready layers in the canonical CRS (EPSG:32647) | Every file has a `<file>.provenance.json` sidecar. |

Conventions:

- Store original archives and their checksum; never trust a re-download to be
  identical.
- Source licences may forbid redistribution. Keeping data out of Git is also a
  licensing safeguard, not only a size one.
- Synthetic test geometry lives in `tests/fixtures/`, never here.
