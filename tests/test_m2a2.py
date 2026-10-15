# ruff: noqa: E501
"""M2A.2: manual-import contract, source-state semantics, MoPH classification, frozen routing."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

from hearthmap.family import load_config
from hearthmap.family.manual import (
    ManualManifestError,
    UnexpectedSchemaError,
    load_import_config,
    load_manifest,
    map_schema,
    qa_manual_table,
    read_table,
    read_xlsx,
    sha256_file,
    verify_manual_file,
)
from hearthmap.family.moph import classify_health_moph, level_code
from hearthmap.provenance import DataSourceEntry, SourceState, load_registry

CFG = load_config()
IMP = load_import_config()
MOE = IMP["sources"]["moe-register-current"]
NEW = Path("outputs/m2a2/family-infrastructure-evidence.parquet")
PREV = Path("outputs/m2a1/family-infrastructure-evidence.parquet")
OLD = Path("outputs/m2a/family-infrastructure-evidence.parquet")
FROZEN = "5c35e98882c3ac62"
TODAY = dt.date(2026, 10, 16)


def make_xlsx(path: Path, header: list[str], rows: list[list]) -> None:
    """A minimal valid .xlsx (inline strings) so no spreadsheet library is needed."""

    def col(i: int) -> str:
        return chr(65 + i)

    def cell(r: int, i: int, v) -> str:
        ref = f"{col(i)}{r}"
        if v is None:
            return ""
        if isinstance(v, int | float):
            return f'<c r="{ref}"><v>{v}</v></c>'
        t = str(v).replace("&", "&amp;").replace("<", "&lt;")
        return f'<c r="{ref}" t="inlineStr"><is><t>{t}</t></is></c>'

    sheet = "".join(
        f'<row r="{r + 1}">' + "".join(cell(r + 1, i, v) for i, v in enumerate(row)) + "</row>"
        for r, row in enumerate([header, *rows])
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="s" sheetId="1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{sheet}</sheetData></worksheet>',
        )


HEADER = ["รหัสสถานศึกษา", "ชื่อสถานศึกษา", "จังหวัด", "ละติจูด", "ลองจิจูด", "ปีการศึกษา"]


def good_rows(n: int = 1600) -> list[list]:
    provs = ["เชียงใหม่", "เชียงราย", "พะเยา"]
    return [
        [
            f"10{i:08d}",
            f"โรงเรียนทดสอบ{i}",
            provs[i % 3],
            18.5 + (i % 100) / 100,
            99.0 + (i % 80) / 100,
            2568,
        ]
        for i in range(n)
    ]


def province_of(lon: float, lat: float) -> str | None:
    return "TH50"  # every synthetic point is treated as inside Chiang Mai


# -- manifest -------------------------------------------------------------------------------------------
def write_manifest(folder: Path, file: Path, **over) -> Path:
    m = {
        "publisher": "Ministry of Education",
        "dataset_title": "ข้อมูลโรงเรียนในประเทศไทย",
        "original_download_url": "https://catalog.moe.go.th/dataset/x",
        "download_date": "2026-10-16",
        "file_name": file.name,
        "file_sha256": sha256_file(file),
        "licence": "Open Data Common",
        "acquired_by": "project owner, browser",
        "notes": "",
    }
    m |= over
    p = folder / "MANIFEST.yaml"
    p.write_text(yaml.safe_dump(m, allow_unicode=True), "utf-8")
    return p


def test_manual_manifest_requires_full_provenance_and_checksum(tmp_path):
    f = tmp_path / "register.xlsx"
    make_xlsx(f, HEADER, good_rows(3))
    man = load_manifest(write_manifest(tmp_path, f))
    assert verify_manual_file(man, tmp_path) == f
    with pytest.raises(ManualManifestError):
        load_manifest(write_manifest(tmp_path, f, licence=""))  # a missing field is refused
    f.write_bytes(f.read_bytes() + b"x")  # the original was altered after the manifest was written
    with pytest.raises(ManualManifestError, match="mismatch"):
        verify_manual_file(man, tmp_path)


def test_manual_manifest_refuses_credentials_in_the_url(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n", "utf-8")
    with pytest.raises(ValueError):
        load_manifest(
            write_manifest(
                tmp_path, f, original_download_url="https://catalog.moe.go.th/dl?apikey=SECRET123"
            )
        )


def test_manifest_template_is_tracked_and_lists_every_required_field():
    t = yaml.safe_load(Path("data/manual/MANIFEST.template.yaml").read_text("utf-8"))
    assert {
        "publisher",
        "dataset_title",
        "original_download_url",
        "download_date",
        "file_name",
        "file_sha256",
        "licence",
        "acquired_by",
        "notes",
    } <= set(t)
    assert Path("data/manual/README.md").exists()


def test_manual_data_directory_is_git_ignored():
    ignore = Path(".gitignore").read_text("utf-8")
    assert "data/manual/*" in ignore and "!data/manual/README.md" in ignore


# -- reading and schema ---------------------------------------------------------------------------------
def test_xlsx_roundtrip_preserves_thai_text_and_numbers(tmp_path):
    f = tmp_path / "w.xlsx"
    make_xlsx(f, HEADER, good_rows(5))
    df = read_xlsx(f)
    assert list(df.columns) == HEADER and len(df) == 5
    assert df["ชื่อสถานศึกษา"].iloc[0] == "โรงเรียนทดสอบ0" and df["ปีการศึกษา"].iloc[0] == 2568
    assert read_table(f).shape == df.shape


def test_unexpected_schema_is_refused_not_guessed():
    with pytest.raises(UnexpectedSchemaError, match="required fields not found"):
        map_schema(["col_a", "col_b", "x"], MOE)
    cols = map_schema(HEADER, MOE)
    assert cols["id"] == "รหัสสถานศึกษา" and cols["lat"] == "ละติจูด" and cols["province"] == "จังหวัด"


# -- QA -------------------------------------------------------------------------------------------------
def qa(rows, **kw):
    df = pd.DataFrame(rows, columns=HEADER)
    return qa_manual_table(df, map_schema(HEADER, MOE), MOE, today=TODAY, **kw)


def test_good_current_file_passes():
    r = qa(good_rows())
    assert (
        r["ok"]
        and r["duplicate_official_ids"] == 0
        and r["missing_coordinates"] == 0
        and r["invalid_coordinates"] == 0
    )
    assert (
        r["records_in_aoi_by_stated_province"] == 1600 and r["latest_internal_date"] == "2025-12-31"
    )


def test_duplicate_official_ids_block_the_import():
    rows = good_rows()
    rows[5][0] = rows[4][0]
    r = qa(rows)
    assert (
        not r["ok"]
        and r["duplicate_official_ids"] == 1
        and any("duplicate" in b for b in r["blocking"])
    )


def test_missing_and_invalid_coordinates_are_counted():
    rows = good_rows()
    rows[0][3] = None  # missing latitude
    rows[1][3], rows[1][4] = 0, 0  # null island
    rows[2][3], rows[2][4] = 99.5, 18.5  # swapped
    r = qa(rows)
    assert r["missing_coordinates"] == 1 and r["invalid_coordinates"] == 2


def test_too_many_invalid_coordinates_block():
    rows = good_rows()
    for i in range(200):
        rows[i][3], rows[i][4] = 0, 0
    r = qa(rows)
    assert not r["ok"] and any("invalid coordinates" in b for b in r["blocking"])


def test_province_mismatch_is_reported():
    r = qa(
        good_rows(), province_of=province_of
    )  # the lookup says TH50 for everything: Chiang Rai/Phayao rows mismatch
    assert r["province_mismatch"] > 1000 and any(
        "outside their stated AOI province" in a for a in r["advisory"]
    )


def test_stale_internal_dates_block_the_import():
    rows = good_rows()
    for r_ in rows:
        r_[5] = 2560  # academic year 2560 BE = 2017
    r = qa(rows)
    assert not r["ok"] and any("not current" in b for b in r["blocking"]) and r["age_years"] > 3


def test_unexpected_aoi_coverage_blocks_the_import():
    r = qa(good_rows(40))
    assert not r["ok"] and any("unexpected coverage" in b for b in r["blocking"])


# -- source-state semantics ------------------------------------------------------------------------------
def entry(**over) -> dict:
    base = {
        "id": "x-test",
        "name": "t",
        "category": "education",
        "priority": "must_have",
        "verification_status": "NEEDS_RESEARCH",
    }
    return base | over


def test_source_state_rules():
    DataSourceEntry(**entry(source_state="SOURCE_EXISTS_AGENT_BLOCKED", acquisition_path="manual"))
    with pytest.raises(ValueError):  # a source the agent could not reach cannot be data_verified
        DataSourceEntry(
            **entry(
                source_state="SOURCE_EXISTS_AGENT_BLOCKED",
                metadata_verified=True,
                data_verified=True,
                acquisition_status="ACQUIRED",
            )
        )
    with pytest.raises(ValueError):  # manual acquisition needs acquired data and a local path
        DataSourceEntry(**entry(source_state="SOURCE_MANUALLY_ACQUIRED"))
    with pytest.raises(ValueError):  # 'unavailable' must cite evidence that it does not exist
        DataSourceEntry(**entry(source_state="SOURCE_UNAVAILABLE"))
    assert len(list(SourceState)) == 4


def test_moe_register_is_blocked_not_unavailable_and_has_a_manual_path():
    reg = load_registry()
    moe = reg.get("schools-official")
    assert (
        moe.source_state is SourceState.SOURCE_EXISTS_AGENT_BLOCKED
        and moe.acquisition_path
        and "manual" in moe.acquisition_path.lower()
    )
    hcode = reg.get("health-facilities-moph")
    assert hcode.source_state is SourceState.SOURCE_EXISTS_AGENT_BLOCKED
    assert (
        "bypass" in (hcode.acquisition_path or "").lower()
        or "bot" in (hcode.verification_evidence or "").lower()
    )
    assert (
        reg.get("facility-moph-hospital-update68").source_state
        is SourceState.SOURCE_EXISTS_AGENT_ACCESSIBLE
    )
    assert not any(
        e.source_state is SourceState.SOURCE_UNAVAILABLE
        for e in reg.sources
        if e.id in ("schools-official", "health-facilities-moph")
    )


# -- MoPH classification ---------------------------------------------------------------------------------
def test_moph_class_comes_from_source_fields_and_never_infers_capability():
    c = classify_health_moph(
        "โรงพยาบาลศูนย์", "A - โรงพยาบาลศูนย์", "กระทรวงสาธารณสุข", "โรงพยาบาลใด ๆ", "กำลังใช้งาน"
    )
    assert (
        c["facility_class"] == "REGIONAL_REFERRAL_HOSPITAL"
        and c["class_basis"] == "SOURCE_TYPECODE"
        and c["higher_level"]
    )
    assert (
        c["capabilities_source_supported"] == []
    )  # a regional class is not a stated emergency/ICU capability
    g = classify_health_moph(
        "โรงพยาบาลทั่วไป", "S - โรงพยาบาลทั่วไปขนาดใหญ่", "กระทรวงสาธารณสุข", "x", "กำลังใช้งาน"
    )
    assert (
        g["facility_class"] == "GENERAL_HOSPITAL" and not g["higher_level"]
    )  # large general is NOT promoted to higher-level
    assert (
        classify_health_moph("โรงพยาบาลชุมชน", "F2 - ...", "กระทรวงสาธารณสุข", "x", "กำลังใช้งาน")[
            "facility_class"
        ]
        == "COMMUNITY_HOSPITAL"
    )
    assert (
        classify_health_moph("โรงพยาบาลส่งเสริมสุขภาพตำบล", None, "กระทรวงสาธารณสุข", "x", "กำลังใช้งาน")[
            "facility_class"
        ]
        == "PRIMARY_HEALTH_UNIT"
    )


def test_moph_non_service_points_inactive_and_unknown_are_not_service_evidence():
    o = classify_health_moph("สำนักงานสาธารณสุขจังหวัด", None, "กระทรวงสาธารณสุข", "สสจ.", "กำลังใช้งาน")
    assert o["facility_class"] == "OTHER_NON_SERVICE_POINT" and not o["is_service_point"]
    assert not classify_health_moph("โรงพยาบาลชุมชน", None, "x", "x", "ปิดบริการ")["is_active"]
    u = classify_health_moph(None, None, None, "ไม่ทราบ", "กำลังใช้งาน")
    assert (
        u["facility_class"] == "UNKNOWN" and u["class_confidence"] == "NONE"
    )  # nothing is guessed from a name alone
    uni = classify_health_moph(
        "โรงพยาบาล นอก สธ.",
        None,
        "กระทรวงการอุดมศึกษา วิทยาศาสตร์ วิจัยและนวัตกรรม",
        "โรงพยาบาลมหาราชนครเชียงใหม่",
        "กำลังใช้งาน",
    )
    assert (
        uni["facility_class"] == "UNIVERSITY_HOSPITAL"
        and uni["class_basis"] == "SOURCE_MINISTRY_FIELD"
    )
    assert level_code("F2 - โรงพยาบาลชุมชนขนาดกลาง") == "F2" and level_code(None) is None


# -- artifacts -----------------------------------------------------------------------------------------
def need(path: Path) -> pd.DataFrame:
    if not path.exists():
        pytest.skip(f"{path} not built")
    return pd.read_parquet(path)


def test_hybrid_provenance_is_field_level_and_never_makes_a_record_look_wholly_current():
    gpkg = Path("data/processed/m2a2/facilities.gpkg")
    if not gpkg.exists():
        pytest.skip("layer not built")
    import geopandas as gpd

    hl = gpd.read_file(gpkg, layer="health_facilities")
    for c in (
        "location_source",
        "location_vintage",
        "classification_source",
        "classification_freshness",
        "primary_source_current",
    ):
        assert c in hl.columns
    stale_class = hl["classification_source"].str.contains("CITIZENinfo|2020", na=False)
    assert (
        not hl.loc[stale_class, "classification_freshness"].eq("CURRENT_SOURCE_FIELD").any()
    )  # an older class stays marked stale
    assert hl["capabilities_source_supported"].fillna("").eq("").all()


def test_education_is_unchanged_when_no_current_moe_register_was_supplied():
    new, prev = need(NEW), need(PREV)
    for c in (
        "primary_school",
        "secondary_school",
        "kindergarten",
        "early_childhood_centre",
        "vocational_institution",
        "university",
    ):
        pd.testing.assert_series_equal(
            new[f"nearest_{c}_id"].reset_index(drop=True),
            prev[f"nearest_{c}_id"].reset_index(drop=True),
        )
        pd.testing.assert_series_equal(
            new[f"drive_time_to_nearest_{c}_min"].reset_index(drop=True),
            prev[f"drive_time_to_nearest_{c}_min"].reset_index(drop=True),
        )
    assert (
        new["education_primary_source_vintage"].eq("DOPA_2021_STALE_FALLBACK").all()
    )  # still labelled stale


def test_routing_is_frozen_and_road_columns_unchanged_after_the_health_refresh():
    fp = hashlib.sha256(json.dumps(CFG["travel_time"], sort_keys=True).encode()).hexdigest()[:16]
    assert fp == FROZEN
    new, old = need(NEW), need(OLD)
    assert (
        new["routing_config_fingerprint"].unique().tolist() == [FROZEN]
        and new["routing_basis"].eq("BASELINE_DRIVE_TIME").all()
    )
    for c in ("road_snap_distance_m", "road_access_context", "nearest_major_road_distance_m"):
        pd.testing.assert_series_equal(old[c], new[c])


def test_higher_level_hospital_is_computed_only_from_a_source_stated_level():
    new = need(NEW)
    assert new[
        "route_available_higher_level_hospital"
    ].any()  # the public MoPH layer states a regional class
    assert (
        new["hospital_level_status"].str.startswith("AVAILABLE_FROM_PUBLIC_MOPH_POINT_LAYER").all()
    )
    failed = ~new["route_available_higher_level_hospital"]
    assert (
        new.loc[failed, "drive_time_to_nearest_higher_level_hospital_min"].isna().all()
    )  # unroutable cells stay unresolved
    assert (new.loc[failed, "higher_level_hospital_unresolved_reason"] != "").all()
    assert not [c for c in new.columns if "score" in c.lower()]


def test_utilities_and_hazard_actions_carry_forward_unchanged():
    new = need(NEW)
    assert (
        new["electricity_service_potential"].eq("NOT_ASSESSED").all()
        and new["water_service_context"].eq("NON_PWA_OR_UNKNOWN_SERVICE").all()
    )
    assert new["telecom_evidence"].str.startswith("DEFERRED").all()
    m1e = Path("outputs/m1e/natural-hazard-actions.parquet")
    if m1e.exists():
        haz = pd.read_parquet(m1e)
        cols = [
            c
            for c in haz.columns
            if c.endswith("_action") or c.startswith("natural_hazard") or c == "hazard_action_set"
        ]
        assert cols and not set(cols) & set(new.columns)
        merged = haz.merge(new, on="cell_id", how="left", suffixes=("", "_fam"))
        for c in cols:
            assert merged[c].equals(haz[c])
