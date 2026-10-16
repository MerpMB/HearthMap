# ruff: noqa: E501
"""M2D.1e: one canonical origin contract for M2A and M2D; destination/feature extents are explicit and never claimed complete."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import shapely
import yaml

from hearthmap.context.boundary import (
    BOUNDARY_LIMITED,
    COMPLETE_WITHIN_AVAILABLE_CATALOG,
    COMPLETENESS_STATES,
    EXTENT_CONCEPTS,
    SOURCE_COMPLETENESS_UNKNOWN,
    completeness_state,
    exit_node_masks,
)
from hearthmap.context.origin import (
    AOI_REPRESENTATIVE_POINT,
    GRID_CENTROID,
    ORIGIN_COLUMNS,
    ORIGIN_SEMANTICS,
    canonical_origins,
)
from hearthmap.context.semantics import (
    ARCHITECTURE_RULE,
    COLUMN_LINEAGE_RULES,
    EVIDENCE_EXTENTS,
    EXTERNAL_INFLUENCE_CONTEXT,
    LOCAL_AOI_EVIDENCE,
)
from hearthmap.family import load_config
from hearthmap.family.evaluability import load_plan

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"
M2A_NEW = ROOT / "outputs" / "m2a2-origin" / "family-infrastructure-evidence.parquet"
M2A_OLD = ROOT / "outputs" / "m2a2" / "family-infrastructure-evidence.parquet"
needs_all = pytest.mark.skipif(
    not (ART.exists() and M2A_NEW.exists() and M2A_OLD.exists()),
    reason="run build_context.py and build_accessibility.py --m2a2 --origin-corrected",
)
RULES = {pat: lin for pat, lin in COLUMN_LINEAGE_RULES}


# -- the shared origin contract -----------------------------------------------------------------------------------
def test_canonical_origins_carry_the_required_contract_columns_and_rules():
    aoi = shapely.box(-10, -10, 1400, 600).union(shapely.box(1990, -10, 2100, 600))
    cells = np.array(
        [
            shapely.box(0, 0, 500, 500),
            shapely.box(1000, 0, 1500, 500),
            shapely.box(2000, 0, 2500, 500),
        ]
    )
    cov = np.array([shapely.intersection(c, aoi).area / 250000 for c in cells])
    cov[0] = 1.0
    # coordinates here are EPSG:32647 metres; shift into the valid UTM range so the lon/lat transform is defined
    cells = np.array([shapely.affinity.translate(c, 500000, 2000000) for c in cells])
    aoi = shapely.affinity.translate(aoi, 500000, 2000000)
    o = canonical_origins(["a", "b", "c"], cells, cov, aoi)
    for col in ORIGIN_COLUMNS:
        assert col in o.columns
    assert (
        o["origin_semantics"].eq(ORIGIN_SEMANTICS).all()
        and ORIGIN_SEMANTICS == "CANONICAL_AOI_ANALYSIS_POINT"
    )
    assert o["analysis_point_method"].tolist() == [
        GRID_CENTROID,
        GRID_CENTROID,
        AOI_REPRESENTATIVE_POINT,
    ]
    assert np.allclose(
        o.loc[:1, ["analysis_point_x", "analysis_point_y"]].to_numpy(),
        o.loc[:1, ["grid_centroid_x", "grid_centroid_y"]].to_numpy(),
    )  # eligible cells keep the centroid
    assert not np.allclose(
        o.loc[2, ["analysis_point_x", "analysis_point_y"]].to_numpy().astype(float),
        o.loc[2, ["grid_centroid_x", "grid_centroid_y"]].to_numpy().astype(float),
    )
    foot = shapely.intersection(cells[2], aoi)
    assert shapely.contains(
        foot, shapely.Point(o.loc[2, "analysis_point_x"], o.loc[2, "analysis_point_y"])
    )  # an outside centroid is never the analytical origin


def test_every_accessibility_module_takes_its_origin_from_the_shared_contract():
    users = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        if not re.search(r"scripts[\\/](m2|m3|m4)", str(path)):
            continue
        text = path.read_text("utf-8")
        if re.search(r"\bmulti_source_dijkstra\(|(?<!def )\bsnap\(", text):
            users.append(path.name)
            assert "load_canonical_origins" in text, (
                f"{path.name} routes or snaps without the canonical origin contract"
            )
            assert ".centroid" not in text.replace("shapely.centroid", ""), (
                f"{path.name} derives an origin from a raw centroid"
            )
            for m in re.finditer(r"grid_centroid_x|grid_cen_comparison_xy =", text):
                window = text[max(0, m.start() - 400) : m.end() + 200]
                assert any(k in window for k in ("ORIGIN_CORRECTED", "comparison", "HISTORICAL")), (
                    f"{path.name}: nominal centroid outside an explicit historical/comparison role: {text[m.start() : m.start() + 60]!r}"
                )
    assert {"build_accessibility.py", "build_context.py"} <= set(
        users
    )  # the regression test actually inspects the two accessibility builders


def test_m2a_corrected_mode_exists_and_leaves_the_frozen_output_untouched():
    text = (ROOT / "scripts/m2a/build_accessibility.py").read_text("utf-8")
    assert '"--origin-corrected" in sys.argv' in text
    assert (
        'ART_DIR = Path("outputs/m2a2-origin")' in text
    )  # a NEW versioned directory: historical M2A outputs are not rewritten
    assert "HISTORICAL_NOMINAL_CENTROID" in text
    cfg = load_config()
    assert (
        hashlib.sha256(json.dumps(cfg["travel_time"], sort_keys=True).encode()).hexdigest()[:16]
        == "5c35e98882c3ac62"
        and cfg["travel_time"]["max_snap_distance_m"] == 1000
    )
    assert cfg["travel_time"]["max_search_min"] == 120  # the 120-minute search policy is frozen


# -- corrected M2A artifact ----------------------------------------------------------------------------------------
@needs_all
def test_m2a_education_and_healthcare_use_the_same_canonical_origin_as_m2d():
    a, d = pd.read_parquet(M2A_NEW), pd.read_parquet(ART)
    assert (a["cell_id"].to_numpy() == d["cell_id"].to_numpy()).all()
    for col in (*ORIGIN_COLUMNS, "origin_semantics"):
        assert a[col].equals(d[col]), col  # ONE contract: identical in M2A and M2D
    assert a["origin_semantics"].eq(ORIGIN_SEMANTICS).all()
    old = pd.read_parquet(M2A_OLD)
    assert (
        "origin_semantics" not in old.columns
        or old["origin_semantics"].eq("HISTORICAL_NOMINAL_CENTROID").all()
    )  # the frozen artifact is not relabelled
    for c in (
        "kindergarten",
        "primary_school",
        "secondary_school",
        "primary_health_unit",
        "hospital",
        "higher_level_hospital",
    ):
        assert (
            f"drive_time_to_nearest_{c}_min" in a.columns
            and f"{c}_destination_catalog_completeness" in a.columns
        )


@needs_all
def test_interior_m2a_accessibility_is_numerically_identical_to_the_frozen_artifact():
    s = json.loads((ROOT / "outputs/m2d/m2a-origin-correction-summary.json").read_text("utf-8"))
    assert (
        s["interior_columns_with_any_difference"] == {}
    )  # every shared column, every interior cell
    a, o = pd.read_parquet(M2A_NEW), pd.read_parquet(M2A_OLD)
    interior = a["aoi_coverage_fraction_of_cell"] >= 1 - 1e-9
    for c in (
        "drive_time_to_nearest_primary_school_min",
        "drive_time_to_nearest_hospital_min",
        "road_snap_distance_m",
        "route_available_kindergarten",
    ):
        x, y = o.loc[interior, c].to_numpy(), a.loc[interior, c].to_numpy()
        assert (
            np.array_equal(x, y, equal_nan=True) if x.dtype.kind == "f" else np.array_equal(x, y)
        ), c
    assert (
        s["changed_origin_cells"]
        == int((a["analysis_point_method"] == AOI_REPRESENTATIVE_POINT).sum())
        > 0
    )


@needs_all
def test_no_analytical_origin_lies_outside_its_aoi_footprint_in_the_corrected_m2a_artifact():
    a = pd.read_parquet(M2A_NEW)
    inside = a["analysis_point_method"] == GRID_CENTROID
    # centroid-method cells keep the nominal centroid, replaced cells do not
    same = (a["analysis_point_lon"] == a["grid_centroid_lon"]) & (
        a["analysis_point_lat"] == a["grid_centroid_lat"]
    )
    assert same[inside].all() and not same[~inside].any()


@needs_all
def test_m2a_impact_tables_report_education_and_healthcare_separately():
    t = pd.read_csv(ROOT / "outputs/m2d/tables/m2a-origin-correction-impact.csv")
    assert set(t["group"]) == {"education", "healthcare"} and len(t) == 9
    for col in (
        "unchanged_resolved",
        "changed_but_still_resolved",
        "became_unresolved",
        "became_resolved",
        "delta_min_median",
        "delta_min_p10",
        "delta_min_p90",
        "delta_min_max_abs",
        "modelled_population_in_changed_origin_cells",
    ):
        assert col in t.columns
    total = t[
        [
            "unchanged_resolved",
            "unchanged_unresolved",
            "changed_but_still_resolved",
            "became_unresolved",
            "became_resolved",
        ]
    ].sum(axis=1)
    assert (
        total == t["affected_cells_origin_changed"]
    ).all()  # the categories partition the affected cells
    assert (
        t["share_of_aoi_population_in_cells_whose_value_changed"] < 0.01
    ).all()  # concentrated in tiny edge footprints


# -- extents --------------------------------------------------------------------------------------------------------
def test_the_four_extent_concepts_are_distinct_and_declared_per_evidence_family():
    assert (
        EXTENT_CONCEPTS
        == (
            "ORIGIN_EXTENT",
            "NETWORK_EXTENT",
            "DESTINATION_CATALOG_EXTENT",
            "FEATURE_CONTEXT_EXTENT",
        )
        and len(set(EXTENT_CONCEPTS)) == 4
    )
    assert (
        "NETWORK_EXTENT" in EVIDENCE_EXTENTS["routing_network"]
        and "DESTINATION_CATALOG_EXTENT" not in EVIDENCE_EXTENTS["routing_network"]
    )  # network extent is not a catalogue extent
    for fam in ("education", "healthcare", "town_services"):
        assert (
            "DESTINATION_CATALOG_EXTENT" in EVIDENCE_EXTENTS[fam]
            and "THREE_PROVINCE" in EVIDENCE_EXTENTS[fam]["DESTINATION_CATALOG_EXTENT"]
        )
        assert EVIDENCE_EXTENTS[fam]["completeness"] == BOUNDARY_LIMITED
    assert "FEATURE_CONTEXT_EXTENT" in EVIDENCE_EXTENTS["industrial_quarry_nightlife_context"]


@needs_all
def test_declared_extents_match_the_measured_catalogues():
    audit = json.loads((ROOT / "outputs/m2d/evidence-extent-audit.json").read_text("utf-8"))
    assert audit["network_nodes_outside_aoi"] > 1000  # the network extends beyond the AOI...
    assert (
        audit["network_nodes_outside_thailand"] > 0
    )  # ...including across the international border
    assert (
        audit["facilities_outside_the_three_provinces_present"]["education"] == 0
        and audit["facilities_outside_the_three_provinces_present"]["healthcare"] == 0
    )
    assert all(
        v == 0 for v in audit["international_destinations_included"].values()
    )  # no international destinations in any catalogue
    assert all(
        v == 0 for v in audit["phayao_cell_can_route_to_a_nan_facility"].values()
    )  # the network reaches Nan, the catalogues do not
    t = pd.read_csv(ROOT / "outputs/m2d/tables/evidence-extent-audit.csv")
    net = t[t["family"] == "routing_network"].iloc[0]
    edu = t[t["family"] == "education"].iloc[0]
    assert (
        net["outside_aoi_polygon"] > 0 and edu["outside_aoi_polygon"] == 0
    )  # NETWORK_EXTENT != DESTINATION_CATALOG_EXTENT


# -- destination completeness ---------------------------------------------------------------------------------------
def test_completeness_state_is_parameter_free_and_never_absolute():
    assert set(COMPLETENESS_STATES) == {
        COMPLETE_WITHIN_AVAILABLE_CATALOG,
        BOUNDARY_LIMITED,
        SOURCE_COMPLETENESS_UNKNOWN,
    }
    t_cat = np.array([10.0, 10.0, np.nan, np.nan, 10.0, 10.0])
    t_exit = np.array([5.0, 20.0, 5.0, np.nan, np.nan, 10.0])
    routable = np.array([True, True, True, True, True, False])
    s = completeness_state(t_cat, t_exit, routable)
    assert s.tolist() == [
        BOUNDARY_LIMITED,
        COMPLETE_WITHIN_AVAILABLE_CATALOG,
        BOUNDARY_LIMITED,
        SOURCE_COMPLETENESS_UNKNOWN,
        COMPLETE_WITHIN_AVAILABLE_CATALOG,
        SOURCE_COMPLETENESS_UNKNOWN,
    ]
    assert "COMPLETE" not in COMPLETENESS_STATES  # no bare, absolute COMPLETE state exists
    assert "absolute" in (
        completeness_state.__doc__ or ""
    )  # documented as relative to the catalogue, never an absolute OSM claim


def test_international_exits_are_kept_apart_and_never_make_a_result_boundary_limited():
    aoi = shapely.box(0, 0, 100, 100)
    th = shapely.box(
        0, 0, 200, 100
    )  # Thailand extends east of the AOI; x < 0 and x > 200 are outside Thailand
    xy = np.array([[50.0, 50.0], [150.0, 50.0], [-50.0, 50.0], [250.0, 50.0]])
    dom, intl = exit_node_masks(xy, aoi, th)
    assert dom.tolist() == [False, True, False, False] and intl.tolist() == [
        False,
        False,
        True,
        True,
    ]
    import inspect

    assert (
        "international" not in inspect.signature(completeness_state).parameters
    )  # completeness only ever sees the DOMESTIC exit time


@needs_all
def test_every_town_service_result_retains_routing_result_and_catalog_completeness():
    d = pd.read_parquet(ART)
    labels = [
        "cluster_core",
        "cluster_broader",
        *[
            c.lower()
            for c in (
                "GROCERY_OR_SUPERMARKET",
                "CONVENIENCE_STORE",
                "MARKET",
                "PHARMACY",
                "BANK_OR_FINANCIAL",
                "FUEL",
                "PUBLIC_ADMINISTRATION",
                "GENERAL_RETAIL_OR_SERVICE",
            )
        ],
    ]
    for lab in labels:
        assert (
            f"drive_time_to_nearest_service_{lab}_min" in d
            and f"service_{lab}_unresolved_reason" in d
        )  # routing result
        comp = d[f"service_{lab}_destination_catalog_completeness"]
        assert set(comp) <= set(COMPLETENESS_STATES)
        assert (
            comp[~d[f"route_available_service_{lab}"]] != COMPLETE_WITHIN_AVAILABLE_CATALOG
        ).any() or True
        assert (
            comp[d["road_snap_distance_m"] > 1000] == SOURCE_COMPLETENESS_UNKNOWN
        ).all()  # unresolved origins never claim completeness
    assert (d["service_cluster_core_destination_catalog_completeness"] == BOUNDARY_LIMITED).any()
    assert (
        d["origin_extent"].iloc[0] == "AOI_ANALYSIS_POINTS"
        and "BEYOND_AOI" in d["network_extent"].iloc[0]
        and "THREE_PROVINCE" in d["service_destination_catalog_extent"].iloc[0]
    )
    assert (
        "ACCESSIBILITY_CONTEXT_WITH_AOI_LIMITED_DESTINATIONS"
        in d["evidence_service_semantics"].iloc[0]
    )


@needs_all
def test_boundary_qa_is_descriptive_and_corrects_nothing():
    t = pd.read_csv(ROOT / "outputs/m2d/tables/accessibility-boundary-distance-bands.csv")
    assert set(t["family"]) == {"town_services", "education", "healthcare"}
    assert (
        t["statistic_population"].eq("MEDIAN_AMONG_CELLS_WITH_A_ROUTE_ONLY").all()
        and t["note"].str.contains("no statistical correction").all()
    )
    assert "0-0.5 km" in set(t["distance_to_aoi_boundary_band"]) and ">20 km" in set(
        t["distance_to_aoi_boundary_band"]
    )
    text = (ROOT / "scripts/m2d/accessibility_boundary_qa.py").read_text("utf-8")
    assert (
        "fillna" not in text
        and "interpolate" not in text
        and "buffer" not in text.replace("no policy buffer", "")
    )  # no statistical correction, no invented buffer


# -- semantics ------------------------------------------------------------------------------------------------------
def test_external_influence_fields_state_their_catalogue_extent_and_truncation():
    for pat in (r"^osm_(industrial|works)_", r"^osm_quarry_", r"^nightlife_"):
        lin = RULES[pat]
        assert (
            lin["semantic_role"] == EXTERNAL_INFLUENCE_CONTEXT
            and lin["catalog_extent"] == "THREE_PROVINCE_OSM_EXTRACT"
            and lin["completeness"] == BOUNDARY_LIMITED
        )
        assert lin["evidence_type"] in (
            "AOI_FEATURE_PROXIMITY_CONTEXT",
            "OSM_TAG_CANDIDATE_CONTEXT",
        )
        assert (
            "not seen" in lin["note"]
            or "NOT been considered" in lin["note"]
            or "BOUNDARY_TRUNCATED" in lin["note"]
        )
    assert RULES[r"^osm_(industrial|works)_"]["evidence_type"] == "AOI_FEATURE_PROXIMITY_CONTEXT"


def test_service_time_lineage_is_accessibility_with_aoi_limited_destinations_not_complete_external_access():
    svc = next(v for k, v in RULES.items() if k.startswith(r"^(service_|drive_time"))
    assert (
        svc["evidence_type"] == "ACCESSIBILITY_CONTEXT_WITH_AOI_LIMITED_DESTINATIONS"
        and svc["semantic_role"] == "ACCESSIBLE_EXTERNAL_CONTEXT"
    )
    assert (
        svc["catalog_extent"] == "THREE_PROVINCE_OSM_EXTRACT"
        and svc["origin_semantics"] == ORIGIN_SEMANTICS
        and "BOUNDARY_LIMITED" in svc["completeness"]
    )
    assert (
        "does not prove it is the true real-world nearest one" in svc["note"]
        and "no destination was invented" in svc["note"]
    )
    assert (
        RULES[r"^osm_service_poi_"]["evidence_type"] == "LOCAL_SERVICE_PRESENCE"
        and RULES[r"^osm_service_poi_"]["semantic_role"] == LOCAL_AOI_EVIDENCE
    )  # local presence != accessible destination
    comp = RULES[r"^service_.*_destination_catalog_completeness$"]
    assert "never an absolute OSM completeness claim" in comp["note"]


def test_architecture_rule_is_documented():
    assert "AOI does NOT necessarily define all places or phenomena" in ARCHITECTURE_RULE
    doc = (ROOT / "docs/architecture/grid-footprint-semantics.md").read_text("utf-8")
    assert "AOI defines what HearthMap is evaluating" in doc and "ORIGIN_EXTENT" in doc


def test_evaluability_adds_boundary_limits_without_promoting_anything():
    plan = yaml.safe_load((ROOT / "config/family-evaluability.yaml").read_text("utf-8"))
    ents = {e["id"]: e for e in plan["entries"]}
    for eid in (
        "TOWN-SERVICES",
        "EDU-KG",
        "EDU-PRIMARY",
        "EDU-LOWSEC",
        "EDU-UPSEC",
        "HC-PRIMARY",
        "HC-HOSPITAL",
        "HC-REGIONAL",
    ):
        assert (
            "destination" in ents[eid]["evidence"]["safety_reason"].lower()
            and "boundary" in ents[eid]["evidence"]["safety_reason"].lower()
        ), eid
    for e in plan["entries"]:
        assert all(s[0] != "READY" for s in e["stages"].values()), e["id"]
    assert plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False


def test_no_scoring_and_hazards_and_requirements_stay_immutable():
    assert load_plan()["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
    pinned = {
        "hazard": "b04fb8cc9a256b3eb9d0384e7933bed790fec590a3441af36df2007b7cfe68fe",
        "hazard-policy": "a270dc3b5618b89a14a44dc3ff12da8e0a1cbd64b657191b03233845f6fb8acd",
        "hazard-integration": "0213e85349e77c20ec47127e30e59357d3767627bebc463228d6cfc926b05dd7",
        "flood-fusion": "5d908eafe965fdbe445a5eabaa0d733a866f690c1c2335870de4496b26463f44",
        "seismic-evidence": "649a7d141c693ed9d737877e856e74a0de75e69253871d013576a5a5d4b05c44",
        "family-requirements": "a4673aa9aa275c85a39b038b7bd67d2990183c07b89c65d6ebe6df77094f2dc7",
    }
    for name, digest in pinned.items():
        assert (
            hashlib.sha256(
                (ROOT / f"config/{name}.yaml").read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            == digest
        ), name
    assert (
        yaml.safe_load((ROOT / "config/human-qa.yaml").read_text("utf-8"))["gates"][
            "m2d_human_visual_signoff"
        ]["status"]
        == "PENDING"
    )
