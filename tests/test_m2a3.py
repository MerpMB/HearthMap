"""M2A.3: MOE CKAN outage semantics and the Data Virtualization source role."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from hearthmap.family.reconcile import FacilitySource, compose_primary
from hearthmap.provenance import Availability, DataSourceEntry, SourceState, load_registry


def entry(**over) -> dict:
    return {
        "id": "x-test",
        "name": "t",
        "category": "education",
        "priority": "must_have",
        "verification_status": "NEEDS_RESEARCH",
    } | over


def test_moe_ckan_is_temporarily_unreachable_not_unavailable():
    moe = load_registry().get("schools-official")
    assert moe.source_state is SourceState.SOURCE_EXISTS_AGENT_BLOCKED  # exists
    assert moe.availability is Availability.TEMPORARILY_UNREACHABLE
    assert moe.last_access_attempt == dt.date(2026, 10, 16)
    assert "dataset_04_25660427" in (moe.landing_page or "")
    assert (
        moe.source_state is not SourceState.SOURCE_UNAVAILABLE
        and moe.availability is not Availability.PERMANENTLY_UNAVAILABLE
    )
    assert (
        "do not retry repeatedly" in (moe.verification_evidence or "").lower()
    )  # the outage is recorded as server-side


def test_availability_rules():
    DataSourceEntry(
        **entry(
            source_state="SOURCE_EXISTS_AGENT_BLOCKED",
            availability="TEMPORARILY_UNREACHABLE",
            last_access_attempt="2026-10-16",
        )
    )
    with pytest.raises(ValueError):  # an unreachable source must say when it was last tried
        DataSourceEntry(
            **entry(
                source_state="SOURCE_EXISTS_AGENT_BLOCKED", availability="TEMPORARILY_UNREACHABLE"
            )
        )
    with pytest.raises(
        ValueError
    ):  # permanent unavailability needs SOURCE_UNAVAILABLE (and its evidence)
        DataSourceEntry(**entry(availability="PERMANENTLY_UNAVAILABLE"))
    with pytest.raises(ValueError):  # a temporary outage is not 'unavailable'
        DataSourceEntry(
            **entry(
                source_state="SOURCE_UNAVAILABLE",
                verification_evidence="x",
                availability="TEMPORARILY_UNREACHABLE",
                last_access_attempt="2026-10-16",
            )
        )


def test_data_virtualization_is_validation_evidence_not_a_primary_location_register():
    dv = load_registry().get("moe-data-virtualization-student-report")
    assert dv.role is not None and dv.role.value == "VALIDATION_ONLY"
    assert "NOT_PRIMARY_LOCATION_REGISTER" in (dv.evidence_role or "")
    assert not dv.data_verified and dv.local_raw_path is None  # nothing was extracted
    assert "NOT_SUITABLE_AS_PRIMARY_LOCATION_REGISTER" in " ".join(dv.known_limitations)
    assert dv.permitted_uses == []  # no analytical use is granted
    assert (
        "undocumented" in " ".join(dv.known_limitations).lower()
    )  # the Power BI query service was not used


def test_a_validation_only_source_cannot_become_the_primary_layer():
    import pandas as pd

    layer = pd.DataFrame([{"rec_id": "a", "name": "n", "x": 0.0, "y": 0.0}])
    with pytest.raises(ValueError):
        compose_primary(
            layer, FacilitySource("MOE DV report", 2026, "CURRENT_VALIDATION", current=True), {}
        )


def test_inspection_record_stores_no_capability_url_and_no_data_rows():
    f = Path("outputs/m2a3-review/inp-moe-inspection.json")
    if not f.exists():
        pytest.skip("inspection not run")
    text = f.read_text("utf-8")
    assert (
        "app.powerbi.com/view" not in text and "eyJrIjoi" not in text
    )  # the Power BI embed key is a capability URL
    d = json.loads(text)
    assert d["documented_api"] is None and d["export_control_in_html"] is None
    assert "NOT_SUITABLE_AS_PRIMARY_LOCATION_REGISTER" in d["verdict"]
    assert "latitude" in d["observed_in_browser"]["fields_NOT_seen"]
    assert not any(
        k in d for k in ("rows", "records", "schools")
    )  # observations only, no extracted table
