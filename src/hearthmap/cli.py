"""Command-line entry point: ``hearthmap <command>``."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from hearthmap.config import ConfigError, load_project_config
from hearthmap.enums import Confidence
from hearthmap.provenance import (
    DEFAULT_REGISTRY_PATH,
    ProvenanceRecord,
    current_code_version,
    load_registry,
)
from hearthmap.spatial import BBox, GridSpec, crs_label, generate_grid


def _cmd_check_config(args: argparse.Namespace) -> int:
    cfg = load_project_config(args.config_dir)
    s = cfg.scoring
    print(f"config OK ({cfg.config_dir})")
    print(f"  regions enabled : {', '.join(r.id for r in cfg.regions.enabled_regions)}")
    print(f"  canonical CRS   : {cfg.spatial.crs.canonical}")
    print(f"  grid cell size  : {cfg.spatial.grid.cell_size_m:g} m ({cfg.spatial.grid.selection})")
    print(f"  scoring model   : {s.model_id} {s.model_version} [{s.status}]")
    for dim_id, w in s.normalized_weights().items():
        print(f"    {dim_id:<20} {w:6.1%}")
    undefined = [c.id for c in s.enabled_constraints if not c.rule_defined]
    enabled = len(s.enabled_constraints)
    print(f"  hard constraints: {enabled} enabled, {len(undefined)} without a rule yet")
    return 0


def _cmd_check_registry(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    by_status = Counter(s.verification_status.value for s in reg.sources)
    by_priority = Counter(s.priority for s in reg.sources)
    print(f"registry OK ({args.registry}): {len(reg.sources)} sources")
    print("  verification: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    print("  priority    : " + ", ".join(f"{k}={v}" for k, v in sorted(by_priority.items())))
    return 0


def _cmd_make_grid(args: argparse.Namespace) -> int:
    # Imported lazily so config/registry commands stay fast.
    from hearthmap.ingestion import read_vector_source
    from hearthmap.validation import validate_layer

    cfg = load_project_config(args.config_dir)
    if not args.synthetic:
        if not args.source_id:
            print("error: --source-id is required for real boundary data", file=sys.stderr)
            return 2
        registry = load_registry(args.registry)
        if args.source_id not in registry:
            print(f"error: {args.source_id!r} is not in the data-source registry", file=sys.stderr)
            return 2
        source_confidence = registry.get(args.source_id).confidence
    else:
        source_confidence = Confidence.UNKNOWN

    source_id = args.source_id or "synthetic-fixture"
    boundary, source_ref = read_vector_source(
        args.boundary, source_id=source_id, layer=args.layer, synthetic=args.synthetic
    )

    env = cfg.regions.study_area.sanity_envelope
    report = validate_layer(boundary, name="boundary", envelope=BBox(*env.bounds, crs=env.crs))
    print(report.summary())
    if not report.ok:
        return 1

    grid_cfg = cfg.spatial.grid
    spec = GridSpec(
        cell_size_m=args.cell_size or grid_cfg.cell_size_m,
        crs=cfg.spatial.crs.canonical,
        selection=grid_cfg.selection,
        id_prefix=grid_cfg.id_prefix,
        max_cells=grid_cfg.max_cells,
    )
    grid = generate_grid(boundary, spec)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.to_file(out, layer="grid", driver="GPKG")

    record = ProvenanceRecord(
        artifact_id=f"grid-{spec.cell_size_m:g}m",
        artifact_path=out.as_posix(),
        code_version=current_code_version(),
        sources=[source_ref],
        normalized_crs=crs_label(spec.crs),
        method=(
            f"Square cells of {spec.cell_size_m:g} m aligned to multiples of the cell size in "
            f"{spec.crs}; selection '{spec.selection}' against the union of boundary features."
        ),
        spatial_resolution=f"{spec.cell_size_m:g} m grid",
        confidence=source_confidence,
        limitations=["Grid edge accuracy is limited by the boundary dataset's generalisation."],
        synthetic=args.synthetic,
    )
    record = (
        record.with_step(
            "read", "read boundary layer", path=source_ref.local_path, layer=args.layer
        )
        .with_step(
            "validate", "CRS, geometry and sanity-envelope checks", envelope=list(env.bounds)
        )
        .with_step(
            "reproject",
            "reproject boundary",
            source_crs=source_ref.original_crs,
            target_crs=spec.crs,
        )
        .with_step(
            "grid",
            "generate aligned grid",
            cell_size_m=spec.cell_size_m,
            selection=spec.selection,
            cells=len(grid),
        )
        .with_step("write", "write GeoPackage layer 'grid'", path=out.as_posix())
    )
    sidecar = record.write_sidecar(out)
    print(f"wrote {len(grid):,} cells -> {out}")
    print(f"provenance -> {sidecar}")
    if args.synthetic:
        print("NOTE: input marked SYNTHETIC; output is not real geography.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hearthmap", description=__doc__)
    parser.add_argument("--config-dir", default="config", help="directory with YAML config")
    parser.add_argument(
        "--registry", default=str(DEFAULT_REGISTRY_PATH), help="data-source registry YAML"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-config", help="validate configuration files").set_defaults(
        func=_cmd_check_config
    )
    sub.add_parser("check-registry", help="validate the data-source registry").set_defaults(
        func=_cmd_check_registry
    )

    grid = sub.add_parser("make-grid", help="generate an analysis grid from a boundary file")
    grid.add_argument("--boundary", required=True, help="boundary vector file (must carry a CRS)")
    grid.add_argument("--layer", default=None, help="layer name inside the boundary file")
    grid.add_argument("--out", required=True, help="output GeoPackage path")
    grid.add_argument("--source-id", default=None, help="registry id of the boundary dataset")
    grid.add_argument("--cell-size", type=float, default=None, help="override grid cell size (m)")
    grid.add_argument(
        "--synthetic",
        action="store_true",
        help="input is synthetic test geometry (marked in provenance)",
    )
    grid.set_defaults(func=_cmd_make_grid)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
