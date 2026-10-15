# ruff: noqa: E501
"""M2A.2: validate and register a manually supplied source (MOE register workbook or MoPH HCODE export).

usage: python scripts/m2a2/import_manual.py <source_id>      (source ids: see config/manual-imports.yaml)
Looks for data/manual/<source_id>/MANIFEST.yaml. Exit code 0 = imported, 2 = nothing supplied, 1 = refused.
The original is preserved untouched (copied byte-for-byte after its SHA-256 matches the manifest).
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import shapely

from hearthmap.family.manual import (
    ManualManifestError,
    UnexpectedSchemaError,
    load_import_config,
    load_manifest,
    map_schema,
    qa_manual_table,
    read_table,
    verify_manual_file,
)
from hearthmap.ingestion.acquire import RawArtifact, RawManifest, raw_dir
from hearthmap.provenance.model import sha256_file

REVIEW = Path("outputs/m2a2-review")


def province_lookup():
    prov = gpd.read_file("data/processed/m1a/boundaries.gpkg", layer="province_boundaries").to_crs(
        4326
    )
    geoms = {r.adm1_pcode: r.geometry for r in prov.itertuples()}

    def province_of(lon: float, lat: float) -> str | None:
        p = shapely.Point(lon, lat)
        return next((k for k, g in geoms.items() if g.contains(p)), None)

    return province_of


def main(source_id: str) -> int:
    cfg = load_import_config()
    if source_id not in cfg["sources"]:
        print(f"unknown source id {source_id!r}; known: {list(cfg['sources'])}")
        return 1
    spec = cfg["sources"][source_id]
    folder = Path(cfg["import_dir"]) / source_id
    mpath = folder / "MANIFEST.yaml"
    if not mpath.exists():
        print(f"nothing supplied for {source_id}: expected {mpath} (see data/manual/README.md)")
        return 2
    REVIEW.mkdir(parents=True, exist_ok=True)
    report: dict = {"source_id": source_id, "checked": datetime.now(UTC).isoformat()}
    try:
        manifest = load_manifest(mpath)
        f = verify_manual_file(manifest, folder)
        df = read_table(f)
        cols = map_schema(list(df.columns), spec)
        report |= {
            "file": f.name,
            "sha256": manifest.file_sha256,
            "columns": list(df.columns),
            "mapped_fields": cols,
        }
        report["qa"] = qa_manual_table(
            df,
            cols,
            spec,
            province_of=province_lookup() if cols.get("lat") and cols.get("lon") else None,
        )
    except (ManualManifestError, UnexpectedSchemaError, ValueError) as e:
        report["refused"] = str(e)[:500]
        (REVIEW / f"manual-import-{source_id}.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8"
        )
        print("REFUSED:", report["refused"])
        return 1
    ok = report["qa"]["ok"]
    report["imported"] = False
    if ok:
        dest = raw_dir(
            Path(cfg["raw_dest"]).parent, source_id, f"manual-{manifest.download_date.isoformat()}"
        )
        if (dest / "manifest.json").exists():
            report["note"] = "already imported"
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest / f.name)
            art = RawArtifact(
                original_filename=f.name,
                stored_path=f.name,
                source_url=manifest.original_download_url,
                acquired_at=datetime.combine(
                    manifest.download_date, datetime.min.time(), tzinfo=UTC
                ),
                size_bytes=(dest / f.name).stat().st_size,
                sha256=sha256_file(dest / f.name),
            )
            RawManifest(
                source_id=source_id,
                version=dest.name,
                landing_page=manifest.original_download_url,
                licence=manifest.licence,
                publisher_metadata={
                    "publisher": manifest.publisher,
                    "dataset_title": manifest.dataset_title,
                    "acquired_by": manifest.acquired_by,
                    "acquisition": "MANUAL",
                    "qa_report": f"outputs/m2a2-review/manual-import-{source_id}.json",
                },
                notes=[
                    manifest.notes or "",
                    "Manually supplied; original preserved untouched; checksum verified against the manifest.",
                ],
                artifacts=[art],
            ).write(dest)
        report["imported"] = True
    (REVIEW / f"manual-import-{source_id}.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8"
    )
    print(json.dumps(report["qa"], indent=1, ensure_ascii=False, default=str)[:1500])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
