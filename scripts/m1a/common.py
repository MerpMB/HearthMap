"""Shared helpers for the M1A build scripts (not part of the library API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd

from hearthmap.enums import Confidence
from hearthmap.ingestion.acquire import RawManifest, verify_raw
from hearthmap.provenance import (
    ProvenanceRecord,
    SourceReference,
    TransformationRecord,
    current_code_version,
)

DATA = Path("data")
PROCESSED = DATA / "processed" / "m1a"
VALIDATION = DATA / "interim" / "m1a" / "validation"
OUTPUT_DIR = Path("outputs") / "m1a"
OUTPUT_GPKG = OUTPUT_DIR / "hearthmap-m1a.gpkg"
CANONICAL = "EPSG:32647"
AOI_LONLAT = (97.3, 17.2, 100.9, 20.5)  # area of interest for PROJ operation ranking
AOI_PCODES = ("TH50", "TH56", "TH57")
PROVINCE_NAMES = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}


def raw_source(source_id: str) -> tuple[Path, RawManifest]:
    """Locate the single acquired version of a source and re-verify its checksums."""
    versions = sorted(p for p in (DATA / "raw" / source_id).iterdir() if p.is_dir())
    if len(versions) != 1:
        raise RuntimeError(f"{source_id}: expected exactly one raw version, found {versions}")
    return versions[0], verify_raw(versions[0])


def source_ref(
    source_id: str, *, original_crs: str | None, path: str | None = None
) -> SourceReference:
    d, manifest = raw_source(source_id)
    first = manifest.artifacts[0]
    return SourceReference(
        source_id=source_id,
        source_version=manifest.version,
        acquired_at=first.acquired_at,
        original_crs=original_crs,
        local_path=path or d.as_posix(),
        checksum_sha256=first.sha256 if len(manifest.artifacts) == 1 else None,
    )


def write_layer(
    gdf: gpd.GeoDataFrame,
    path: Path,
    layer: str,
    *,
    sources: list[SourceReference],
    method: str,
    resolution: str,
    confidence: Confidence,
    limitations: list[str],
    transformations: list[TransformationRecord] = (),
    steps: list[tuple[str, str, dict[str, Any]]] = (),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, layer=layer, driver="GPKG")
    rec = ProvenanceRecord(
        artifact_id=f"m1a-{layer}",
        artifact_path=f"{path.as_posix()}#{layer}",
        code_version=current_code_version(),
        sources=sources,
        normalized_crs=CANONICAL,
        method=method,
        spatial_resolution=resolution,
        confidence=confidence,
        limitations=list(limitations),
        crs_transformations=list(transformations),
    )
    for op, desc, params in steps:
        rec = rec.with_step(op, desc, **params)
    side = path.parent / "provenance" / f"{path.stem}.{layer}.provenance.json"
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(rec.to_json() + "\n", encoding="utf-8")
    return side


def write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", "utf-8")
