"""Fail if Git tracks (or is about to track) raw GIS data or large files.

Checks every file that is tracked or staged:
  * geospatial/data extensions are only allowed under tests/fixtures/
  * no file may exceed the size limit (default 1 MB)

Usage:  python scripts/check_repo_hygiene.py [--max-bytes N]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

GIS_EXTENSIONS = {
    ".gpkg", ".shp", ".shx", ".dbf", ".prj", ".cpg", ".fgb", ".parquet", ".geoparquet",
    ".tif", ".tiff", ".vrt", ".nc", ".hdf", ".h5", ".img", ".asc", ".dem", ".kml", ".kmz",
    ".gml", ".osm", ".pbf", ".mbtiles", ".pmtiles", ".duckdb", ".db", ".sqlite", ".geojson",
    ".zip", ".7z", ".gz",
}  # fmt: skip
ALLOWED_PREFIXES = ("tests/fixtures/",)


def tracked_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "-z"], cwd=repo, capture_output=True, check=True
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    problems: list[str] = []
    files = tracked_files(repo)
    for rel in files:
        path = repo / rel
        suffix = path.suffix.lower()
        if suffix in GIS_EXTENSIONS and not rel.startswith(ALLOWED_PREFIXES):
            problems.append(f"GIS/data file tracked outside tests/fixtures/: {rel}")
        if path.is_file() and path.stat().st_size > args.max_bytes:
            problems.append(f"file larger than {args.max_bytes:,} bytes: {rel}")
        if rel.startswith(("data/raw/", "data/interim/", "data/processed/", "outputs/")) and not (
            rel.endswith((".gitkeep", "README.md"))
        ):
            problems.append(f"data/output artifact tracked: {rel}")

    if problems:
        print("Repository hygiene check FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"Repository hygiene OK ({len(files)} tracked files checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
