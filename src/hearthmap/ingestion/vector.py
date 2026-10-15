"""Generic vector reader that records what was read.

Source-specific ingestion pipelines (one per registry entry) arrive in M1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd

from hearthmap.provenance.model import SourceReference, sha256_file
from hearthmap.spatial.crs import crs_label, require_crs


def read_vector_source(
    path: Path | str,
    *,
    source_id: str,
    layer: str | None = None,
    source_version: str | None = None,
    source_date: str | None = None,
    acquired_at: datetime | None = None,
    synthetic: bool = False,
) -> tuple[gpd.GeoDataFrame, SourceReference]:
    """Read a vector file and return it with a :class:`SourceReference`.

    Refuses layers without CRS metadata (spatial.yaml: require_explicit_source_crs).
    ``acquired_at`` defaults to the file's modification time, which only
    approximates the true download time - pass it explicitly when known.
    """
    path = Path(path)
    gdf = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    crs = require_crs(gdf, name=str(path))
    ref = SourceReference(
        source_id=source_id,
        source_version=source_version,
        source_date=source_date,
        acquired_at=acquired_at or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        original_crs=crs_label(crs),
        local_path=path.as_posix(),
        checksum_sha256=sha256_file(path) if path.is_file() else None,
        synthetic=synthetic,
    )
    return gdf, ref
