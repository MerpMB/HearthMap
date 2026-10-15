from __future__ import annotations

import copy
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hearthmap.config import ConfigError
from hearthmap.enums import Confidence, VerificationStatus
from hearthmap.provenance import (
    DataSourceRegistry,
    PermittedUse,
    ProvenanceRecord,
    SourceReference,
    current_code_version,
    load_registry,
    sha256_file,
    sidecar_path,
)
from tests.conftest import REGISTRY_PATH, REPO_ROOT


def _record() -> ProvenanceRecord:
    return ProvenanceRecord(
        artifact_id="grid-500m",
        artifact_path="data/processed/grid.gpkg",
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        code_version="abc123",
        sources=[
            SourceReference(
                source_id="boundaries-ocha-cod-ab",
                source_version="v1",
                acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
                original_crs="EPSG:4326",
                checksum_sha256="0" * 64,
            )
        ],
        normalized_crs="EPSG:32647",
        method="test",
        spatial_resolution="500 m grid",
        confidence=Confidence.MEDIUM,
        limitations=["boundary generalised"],
    )


def test_json_roundtrip_is_lossless():
    rec = _record().with_step(
        "reproject", "to UTM", source_crs="EPSG:4326", target_crs="EPSG:32647"
    )
    restored = ProvenanceRecord.from_json(rec.to_json())
    assert restored == rec
    assert restored.steps[0].parameters["target_crs"] == "EPSG:32647"
    assert restored.confidence is Confidence.MEDIUM


def test_with_step_does_not_mutate_original():
    rec = _record()
    rec2 = rec.with_step("filter", "keep provinces", codes=["50", "56", "57"])
    assert rec.steps == []
    assert [s.operation for s in rec2.steps] == ["filter"]


def test_steps_preserve_order():
    rec = _record().with_step("read", "r").with_step("reproject", "p").with_step("write", "w")
    assert [s.operation for s in rec.steps] == ["read", "reproject", "write"]


def test_sidecar_write_and_read(tmp_path: Path):
    artifact = tmp_path / "grid.gpkg"
    path = _record().write_sidecar(artifact)
    assert path == sidecar_path(artifact)
    assert path.name == "grid.gpkg.provenance.json"
    assert ProvenanceRecord.read_sidecar(artifact) == _record()


def test_unknown_fields_rejected():
    raw = _record().model_dump(mode="json")
    raw["sauce"] = "typo"
    with pytest.raises(ValidationError):
        ProvenanceRecord.model_validate(raw)


def test_defaults_are_conservative():
    rec = ProvenanceRecord(artifact_id="x")
    assert rec.confidence is Confidence.UNKNOWN
    assert rec.synthetic is False
    assert rec.created_at.tzinfo is not None


def test_sha256_file(tmp_path: Path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"hearthmap")
    assert sha256_file(p, chunk_size=4) == hashlib.sha256(b"hearthmap").hexdigest()


def test_code_version_reports_git_commit():
    version = current_code_version(REPO_ROOT)
    assert version == "unknown" or len(version.removesuffix("-dirty")) == 40


# ------------------------------------------------------------ registry


def test_repository_registry_is_valid():
    reg = load_registry(REGISTRY_PATH)
    assert len(reg.sources) > 0
    assert "boundaries-ocha-cod-ab" in reg


def test_repository_registry_verification_state_m1a():
    # Updated deliberately in M1A (was "nothing verified" in M0). Honesty checks:
    reg = load_registry(REGISTRY_PATH)
    verified = reg.by_status(VerificationStatus.VERIFIED)
    assert {s.id for s in verified} == {
        "boundaries-ocha-cod-ab",
        "boundaries-gistda-50k",
        "boundaries-geoboundaries",
        "dem-copernicus-glo30",
        "flood-gistda-repeated-2005-2016",
        "forest-reserve-rfd",
        "protected-gistda-mnre",
        "osm-overpass-aoi",
        # M1B (2026-10-15)
        "landslide-susceptibility-dmr",
        "landslide-inventory-dmr",
    }
    # Every verified source was actually acquired and processed locally.
    assert all(s.local_raw_path and s.processing_status == "PROCESSED" for s in verified)
    # No M1A source is fit for definitive exclusion or parcel-level legal truth yet.
    for s in reg.sources:
        assert PermittedUse.POTENTIAL_HARD_EXCLUSION not in s.permitted_uses
        assert PermittedUse.PARCEL_LEGAL_VERIFICATION not in s.permitted_uses
    # Unverified entries never claim assessed quality.
    assert all(s.confidence is Confidence.UNKNOWN for s in reg.sources if s not in verified)
    # Exactly one PRIMARY boundary source.
    primaries = [s.id for s in reg.sources if s.category == "boundaries" and s.role == "PRIMARY"]
    assert primaries == ["boundaries-ocha-cod-ab"]


def test_forest_reserve_is_legal_warning_only():
    entry = load_registry(REGISTRY_PATH).get("forest-reserve-rfd")
    assert PermittedUse.LEGAL_WARNING_ONLY in entry.permitted_uses
    assert any("certify" in lim for lim in entry.known_limitations)


def _raw_registry() -> dict:
    return copy.deepcopy(yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")))


def test_verified_requires_last_verified():
    raw = _raw_registry()
    raw["sources"][0]["verification_status"] = "VERIFIED"
    raw["sources"][0]["last_verified"] = None
    with pytest.raises(ValidationError, match="VERIFIED entries require"):
        DataSourceRegistry.model_validate(raw)


def test_confidence_requires_inspection():
    raw = _raw_registry()
    entry = next(e for e in raw["sources"] if e["verification_status"] == "NEEDS_RESEARCH")
    entry["confidence"] = "HIGH"
    with pytest.raises(ValidationError, match="claims the data was assessed"):
        DataSourceRegistry.model_validate(raw)


def test_acquired_requires_local_path():
    raw = _raw_registry()
    raw["sources"][0]["processing_status"] = "ACQUIRED"
    raw["sources"][0]["local_raw_path"] = None
    with pytest.raises(ValidationError, match="requires local_raw_path"):
        DataSourceRegistry.model_validate(raw)


def test_duplicate_registry_ids_rejected():
    raw = _raw_registry()
    raw["sources"].append(raw["sources"][0])
    with pytest.raises(ValidationError, match="duplicate source ids"):
        DataSourceRegistry.model_validate(raw)


def test_registry_unknown_category_rejected():
    raw = _raw_registry()
    raw["sources"][0]["category"] = "vibes"
    with pytest.raises(ValidationError):
        DataSourceRegistry.model_validate(raw)


def test_load_registry_wraps_errors(tmp_path: Path):
    bad = tmp_path / "reg.yaml"
    bad.write_text("schema_version: 1\nsources: [{id: X}]\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_registry(bad)


def test_flood_sources_have_explicit_temporal_roles():
    reg = load_registry(REGISTRY_PATH)
    current = reg.get("flood-gistda-repeated-2005-2016")
    assert current.evidence_role == "TEMPORARY_HISTORICAL_EVIDENCE"
    newer = reg.get("flood-gistda-history")
    assert newer.metadata_verified and not newer.data_verified
    assert newer.acquisition_status == "BLOCKED_CREDENTIAL_REQUIRED"
    assert newer.intended_role == "PRIMARY_HISTORICAL_FLOOD_EVIDENCE"
    assert newer.verification_status != VerificationStatus.VERIFIED


def test_verified_requires_data_verified():
    raw = _raw_registry()
    entry = next(e for e in raw["sources"] if e["verification_status"] == "VERIFIED")
    entry["data_verified"] = False
    with pytest.raises(ValidationError, match="data_verified"):
        DataSourceRegistry.model_validate(raw)


def test_data_verified_requires_acquisition():
    raw = _raw_registry()
    entry = next(e for e in raw["sources"] if e["id"] == "flood-gistda-history")
    entry["data_verified"] = True
    with pytest.raises(ValidationError, match="acquired"):
        DataSourceRegistry.model_validate(raw)


def test_landslide_concepts_are_registered_separately():
    reg = load_registry(REGISTRY_PATH)
    roles = {
        s.id: s.evidence_role
        for s in reg.sources
        if s.category == "landslide" and s.evidence_role is not None
    }
    assert roles["landslide-susceptibility-dmr"] == "SUSCEPTIBILITY"
    assert roles["landslide-inventory-dmr"] == "HISTORICAL_EVENT_LOCATIONS"
    assert roles["debris-flow-flash-flood-dmr"] == "MODELLED_IMPACT_AREA"
    susc = reg.get("landslide-susceptibility-dmr")
    assert PermittedUse.POTENTIAL_HARD_EXCLUSION not in susc.permitted_uses
    assert any("NOT published" in lim for lim in susc.known_limitations)
