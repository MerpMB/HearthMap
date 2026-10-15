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

**M1C.1 — Flood truth refresh.** Primary flood evidence is now GISTDA observed
flooding 2011–2023 (2005–2016 kept as corroboration); policy 0.2.0 re-run for
all profiles, still with **no profile selected**. Human visual sign-off M1A.1
and M1B: PASSED. See
[m1c1-flood-refresh-report.md](docs/research/m1c1-flood-refresh-report.md).
The GISTDA API key lives only in the Git-ignored `.env.local` (template:
`.env.example`).

**M1C — Hydrogeomorphic hazard screening policy (provisional).** A regional
screening ladder over the M1B evidence with three sensitivity profiles
(CONSERVATIVE / BALANCED / PERMISSIVE); **no profile is selected** and outcomes
never mean safe, buildable or rejected. Hydrogeomorphic screening only (flood
observed 2005–2016, landslide susceptibility, DSM terrain); not a complete
natural-hazard assessment.
See [m1c-hazard-policy-report.md](docs/research/m1c-hazard-policy-report.md).

Before that, **M1B — Hazard evidence (provisional).** Per-cell flood, landslide (DMR) and DSM-terrain evidence with provisional, explainable interpretations; experimental exclusion candidates and threshold sensitivity only. No exclusions, scores or recommendations; M1A.1 human visual sign-off is PENDING. See [m1b-hazard-evidence-report.md](docs/research/m1b-hazard-evidence-report.md).

Previously: **M1A — Geography truth.** M0 built the foundation; M0.1 corrected it
(datum-transformation contract, legal vs screening evidence, ranking
comparability, area-based overlays); M1A verified and acquired the first real
sources (boundaries, DEM, observed flood history, forest/protected screening,
OSM roads/waterways) and built a validated 500 m grid for Chiang Mai, Chiang
Rai and Phayao. **No location has a suitability score.** See
[m1a-validation-report.md](docs/research/m1a-validation-report.md) and
[roadmap.md](docs/product/roadmap.md).

Data never enters Git. To rebuild M1A locally:

```bash
uv pip install --python .venv -e ".[dev,raster]"
python scripts/m1a/acquire_boundaries.py   # + acquire_flood_gistda / acquire_forest / acquire_osm / acquire_dem
python scripts/m1a/build_boundaries.py
python scripts/m1a/build_dem.py
python scripts/m1a/build_layers.py
python scripts/m1a/package.py               # -> outputs/m1a/hearthmap-m1a.gpkg (open in QGIS)
```

(The COD-AB geodatabase was fetched with `curl`; see its `manifest.json`.)

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
