# HearthMap

Decision-support and geospatial site-selection for finding **areas** in Northern
Thailand (initially Chiang Rai, Chiang Mai, Phayao) that are structurally good
candidates for buying land to build a long-term family home.

HearthMap is **not** a property-listing site. Its order of operations is:

> understand the region → eliminate unsuitable land → score suitable areas →
> identify candidate zones → only later evaluate real parcels/listings.

Explainability, provenance, uncertainty and real-world due diligence take
priority over visually impressive output.

## Status

**M0 — Foundation.** This milestone contains architecture, documentation,
configuration and a small, tested Python core. It contains **no real
geographic data and no real scores.** All spatial tests use explicitly
synthetic geometry. See [docs/product/roadmap.md](docs/product/roadmap.md).

## Quick start

Requires Python 3.12+. Using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv -e ".[dev]"
```

Then (activate `.venv` first, or prefix with `.venv/Scripts/` on Windows):

```bash
pytest
ruff check .
ruff format --check .
hearthmap check-config
hearthmap check-registry
python scripts/check_repo_hygiene.py
```

Generate an analysis grid once a **real, acquired** boundary file exists
(the command refuses files without a CRS and checks the study-area envelope):

```bash
hearthmap make-grid --boundary data/raw/<boundary-file> --out data/processed/grid_500m.gpkg --source-id <registry-id>
```

A `.provenance.json` sidecar is written next to every artifact.

## Repository map

| Path | Purpose |
|---|---|
| `docs/product/` | Vision, requirements, provisional scoring model, roadmap |
| `docs/architecture/` | Architecture overview, spatial/CRS model, decision records |
| `docs/research/` | Data-source registry, data-quality framework, research backlog, open questions |
| `config/` | `regions.yaml`, `spatial.yaml` (CRS + grid), `scoring.yaml` (weights, hard constraints, policies) |
| `src/hearthmap/` | Python package: `config`, `spatial`, `provenance`, `scoring`, `validation`, `ingestion` |
| `data/` | Local data lake (`raw/` → `interim/` → `processed/`), **never committed** |
| `outputs/` | Generated maps/reports, **never committed** |
| `scripts/` | Repository utilities (e.g. hygiene check) |
| `tests/` | pytest suite; `tests/fixtures/` holds synthetic geometry only |

## Core contracts (short version)

1. **Hard exclusion before ranking.** A unit that fails a hard constraint is
   `EXCLUDED` and has `suitability_score = null`. Exclusions are never negative
   points. See [docs/product/scoring-model-v0.1.md](docs/product/scoring-model-v0.1.md).
2. **Missing data is not positive data.** An unevaluated hard constraint makes a
   unit `UNRESOLVED`, not `ELIGIBLE`.
3. **Weights are configuration**, not product truth (`config/scoring.yaml`).
4. **Everything carries provenance and confidence.** See
   [docs/architecture/overview.md](docs/architecture/overview.md).
5. **No false precision.** Coarse data is never presented as fine-grained fact.
