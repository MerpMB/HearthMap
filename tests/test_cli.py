"""End-to-end CLI checks using SYNTHETIC boundary geometry written to tmp_path."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest

from hearthmap.cli import main
from hearthmap.provenance import ProvenanceRecord
from tests.conftest import CONFIG_DIR, REGISTRY_PATH
from tests.fixtures import synthetic

BASE = ["--config-dir", str(CONFIG_DIR), "--registry", str(REGISTRY_PATH)]


def _write(gdf: gpd.GeoDataFrame, path: Path) -> Path:
    gdf.to_file(path, driver="GPKG")
    return path


def test_check_config(capsys):
    assert main([*BASE, "check-config"]) == 0
    assert "EPSG:32647" in capsys.readouterr().out


def test_check_registry(capsys):
    assert main([*BASE, "check-registry"]) == 0
    assert "NEEDS_RESEARCH" in capsys.readouterr().out


def test_bad_config_dir_exits_cleanly(tmp_path, capsys):
    assert main(["--config-dir", str(tmp_path), "check-config"]) == 2
    assert "not found" in capsys.readouterr().err


def test_make_grid_synthetic_end_to_end(tmp_path, capsys):
    boundary = _write(synthetic.aligned_square(2000), tmp_path / "synthetic_boundary.gpkg")
    out = tmp_path / "out" / "grid.gpkg"
    code = main([*BASE, "make-grid", "--boundary", str(boundary), "--out", str(out), "--synthetic"])
    assert code == 0, capsys.readouterr()

    grid = gpd.read_file(out, layer="grid")
    assert len(grid) == 16
    assert grid.crs.to_epsg() == 32647

    rec = ProvenanceRecord.read_sidecar(out)
    assert rec.synthetic is True
    assert rec.sources[0].synthetic is True
    assert rec.sources[0].checksum_sha256
    assert rec.normalized_crs == "EPSG:32647"
    assert [s.operation for s in rec.steps] == ["read", "validate", "reproject", "grid", "write"]
    assert "SYNTHETIC" in capsys.readouterr().out


def test_make_grid_cell_size_override(tmp_path):
    boundary = _write(synthetic.aligned_square(2000), tmp_path / "b.gpkg")
    out = tmp_path / "g.gpkg"
    args = ["make-grid", "--boundary", str(boundary), "--out", str(out), "--synthetic"]
    assert main([*BASE, *args, "--cell-size", "1000"]) == 0
    assert len(gpd.read_file(out)) == 4


def test_make_grid_real_data_requires_registered_source(tmp_path, capsys):
    boundary = _write(synthetic.aligned_square(), tmp_path / "b.gpkg")
    out = tmp_path / "g.gpkg"
    args = ["make-grid", "--boundary", str(boundary), "--out", str(out)]
    assert main([*BASE, *args]) == 2
    assert main([*BASE, *args, "--source-id", "not-in-registry"]) == 2
    assert not out.exists()
    assert "registry" in capsys.readouterr().err


def test_make_grid_rejects_out_of_envelope_boundary(tmp_path):
    # Synthetic UTM coordinates mislabelled as lon/lat -> far outside the envelope.
    bad = synthetic.aligned_square().set_crs("EPSG:4326", allow_override=True)
    boundary = _write(bad, tmp_path / "b.gpkg")
    out = tmp_path / "g.gpkg"
    args = ["make-grid", "--boundary", str(boundary), "--out", str(out), "--synthetic"]
    assert main([*BASE, *args]) == 1
    assert not out.exists()


@pytest.mark.parametrize("cmd", [["--help"], ["make-grid", "--help"]])
def test_help(cmd):
    with pytest.raises(SystemExit) as exc:
        main(cmd)
    assert exc.value.code == 0
