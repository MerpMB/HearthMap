"""M1C.1 contracts: credentials, human QA record, flood-record semantics. SYNTHETIC inputs."""

from __future__ import annotations

import copy
import json
import pickle
from datetime import UTC, datetime

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from hearthmap.hazard import apply_policy, interpret, load_hazard_config, load_policy_config
from hearthmap.hazard.config import HazardConfig
from hearthmap.hazard.policy import HazardPolicyConfig
from hearthmap.ingestion.acquire import RawArtifact, RawManifest
from hearthmap.ingestion.secrets import (
    REDACTED,
    MissingCredentialError,
    is_sanitized,
    load_secret,
    sanitize_url,
    scrub,
)
from hearthmap.qa import SignoffRecord, load_human_qa
from tests.conftest import CONFIG_DIR
from tests.test_hazard import cell as evidence_cell
from tests.test_policy import cell as policy_cell

FAKE = "fake-test-credential-0123456789abcdef"  # synthetic, not a real key
HCFG = load_hazard_config(CONFIG_DIR / "hazard.yaml")
PCFG = load_policy_config(CONFIG_DIR / "hazard-policy.yaml")
PROFILES = ("CONSERVATIVE", "BALANCED", "PERMISSIVE")


# ======================================================== credentials


def test_secret_value_never_appears_in_repr_str_or_pickle(monkeypatch):
    monkeypatch.setenv("HM_TEST_KEY", FAKE)
    s = load_secret("HM_TEST_KEY", env_file=None)
    assert FAKE not in repr(s) and FAKE not in str(s) and FAKE not in f"{s}"
    assert s.reveal() == FAKE
    with pytest.raises(TypeError):
        pickle.dumps(s)


def test_secret_read_from_env_file_and_missing_is_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("HM_TEST_KEY", raising=False)
    f = tmp_path / ".env.local"
    f.write_text(f'# comment\nHM_TEST_KEY="{FAKE}"\n', "utf-8")
    assert load_secret("HM_TEST_KEY", env_file=f).reveal() == FAKE
    with pytest.raises(MissingCredentialError) as exc:
        load_secret("HM_OTHER_KEY", env_file=f)
    assert FAKE not in str(exc.value)


@pytest.mark.parametrize("param", ["api_key", "key", "token", "API_KEY"])
def test_authenticated_urls_are_sanitized(param):
    url = f"https://example.test/flood?{param}={FAKE}&area=%7B%7D&lat=19.1"
    clean = sanitize_url(url)
    assert FAKE not in clean and f"{param}={REDACTED}" in clean
    assert "lat=19.1" in clean and is_sanitized(clean) and not is_sanitized(url)


def test_scrub_removes_value_from_error_text(monkeypatch):
    monkeypatch.setenv("HM_TEST_KEY", FAKE)
    s = load_secret("HM_TEST_KEY", env_file=None)
    assert FAKE not in scrub(f"HTTP 500 for url ...?api_key={FAKE}", s)


def test_raw_manifest_refuses_unsanitized_url():
    kw = {
        "original_filename": "t.json",
        "stored_path": "t.json",
        "acquired_at": datetime.now(UTC),
        "size_bytes": 1,
        "sha256": "0" * 64,
    }
    with pytest.raises(ValidationError, match="credential"):
        RawArtifact(source_url=f"https://x.test/a?api_key={FAKE}", **kw)
    art = RawArtifact(source_url=sanitize_url(f"https://x.test/a?api_key={FAKE}"), **kw)
    m = RawManifest(
        source_id="s",
        version="v",
        publisher_metadata={
            "access_method": "authenticated GISTDA API",
            "credential_source": "environment",
        },
        artifacts=[art],
    )
    assert FAKE not in m.model_dump_json()


def test_env_example_is_a_placeholder_and_local_env_is_ignored():
    import subprocess
    from pathlib import Path

    root = CONFIG_DIR.parent
    example = (root / ".env.example").read_text("utf-8")
    assert "GISTDA_API_KEY=\n" in example
    tracked = subprocess.run(
        ["git", "ls-files", ".env.local", ".env"], cwd=root, capture_output=True, text=True
    ).stdout
    assert tracked.strip() == ""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env.local"], cwd=root, capture_output=True
    )
    assert ignored.returncode == 0
    assert Path(root / ".gitignore").read_text("utf-8").count("!.env.example") == 1


# ======================================================== human QA record


def test_human_qa_gates_persist_and_match_configs():
    qa = load_human_qa(CONFIG_DIR / "human-qa.yaml")
    for gate in ("m1a1_human_visual_signoff", "m1b_human_visual_signoff"):
        rec = qa.gates[gate]
        assert rec.status == "PASSED"
        assert str(rec.review_date) == "2026-10-15"
        assert rec.reviewer_role == "project user"
        assert rec.result == "no blocking visual anomalies observed"
        assert getattr(HCFG.gates, gate) == rec.status
        assert getattr(PCFG.gates, gate) == rec.status
    # M1C pack was not clearly part of the reviewed material: not assumed
    assert qa.status("m1c_human_visual_signoff") == "PENDING"


def test_signoff_record_cannot_be_passed_without_review_details():
    with pytest.raises(ValidationError):
        SignoffRecord(status="PASSED", reviewed_material="x")
    with pytest.raises(ValidationError):
        SignoffRecord(status="PENDING", reviewer_role="someone", reviewed_material="x")


def test_no_profile_selected_even_with_gates_passed():
    assert PCFG.default_profile is None and PCFG.status == "PROVISIONAL"


# ======================================================== flood semantics


def test_flood_config_states_source_period_and_metric():
    ps, ls = HCFG.flood.primary_source, HCFG.flood.legacy_source
    assert (ps.source_id, ps.evidence_period, ps.record_years) == (
        "flood-gistda-history",
        "2011-2023",
        13,
    )
    assert ps.role == "PRIMARY_HISTORICAL_FLOOD_EVIDENCE" and ps.used_for_interpretation
    assert (ls.source_id, ls.record_years, ls.role) == (
        "flood-gistda-repeated-2005-2016",
        12,
        "HISTORICAL_CORROBORATION",
    )
    assert not ls.used_for_interpretation
    fl = PCFG.flood_source
    assert (fl.source_id, fl.period, fl.record_years) == ("flood-gistda-history", "2011-2023", 13)
    assert "13 years" in fl.derived_threshold_semantics


def test_old_and_new_flood_schemas_stay_distinguishable():
    """2005-2016 evidence cannot be fed to thresholds written for 2011-2023."""
    legacy = evidence_cell(
        flood_source_id="flood-gistda-repeated-2005-2016",
        flood_evidence_period="2005-2016",
        flood_record_years=12,
    )
    with pytest.raises(ValueError, match="change meaning"):
        interpret(pd.DataFrame([legacy]), HCFG)
    with pytest.raises(ValueError, match="different meaning"):
        apply_policy(
            pd.DataFrame([policy_cell(flood_evidence_period="2005-2016", flood_record_years=12)]),
            PCFG,
            "BALANCED",
        )
    no_semantics = {k: v for k, v in evidence_cell().items() if k != "flood_source_id"}
    with pytest.raises(KeyError):
        interpret(pd.DataFrame([no_semantics]), HCFG)


def test_legacy_flood_columns_never_change_interpretation_or_policy():
    a = evidence_cell() | policy_cell()
    b = a | {
        "legacy_flood_2005_2016_area_fraction": 0.9,
        "legacy_flood_2005_2016_years_ge3_area_fraction": 0.9,
    }
    ia, ib = interpret(pd.DataFrame([a]), HCFG), interpret(pd.DataFrame([b]), HCFG)
    assert ia["flood_tier"].iloc[0] == ib["flood_tier"].iloc[0] == "NONE_DETECTED"
    for p in PROFILES:
        pa = apply_policy(pd.DataFrame([a]), PCFG, p)
        pb = apply_policy(pd.DataFrame([b]), PCFG, p)
        assert pa.equals(pb)
    assert "legacy_flood_2005_2016_years_ge3_area_fraction" in PCFG.prohibited_evidence_columns


def test_source_native_years_semantics_preserved_in_labels_and_reasons():
    r = interpret(
        pd.DataFrame(
            [
                evidence_cell(flood_years_ge3_area_fraction=0.5, flood_area_fraction=0.6),
                evidence_cell(),
            ]
        ),
        HCFG,
    )
    assert "3 of 13 years (2011-2023)" in r["flood_reason"].iloc[0]
    assert r["flood_state"].iloc[1] == "NO_OBSERVED_FLOOD_IN_2011_2023_RECORD"


def test_missing_flood_polygon_never_becomes_safety():
    r = interpret(pd.DataFrame([evidence_cell()]), HCFG).iloc[0]
    assert r["flood_tier"] == "NONE_DETECTED"
    assert "NOT evidence of no flood risk" in r["flood_reason"]
    assert r["flood_confidence"] == "LOW"
    for word in ("SAFE", "LOW_RISK"):
        assert word not in r["flood_state"]
    for p in PROFILES:
        pr = apply_policy(pd.DataFrame([policy_cell()]), PCFG, p).iloc[0]
        assert pr["regional_search_status"] == "NO_MAJOR_CONCERN_DETECTED"
        assert "NO_OBSERVED_FLOOD_IN_RECORD" in pr["informational_codes"]
        text = PCFG.reason_codes["NO_OBSERVED_FLOOD_IN_RECORD"].format(flood_period="2011-2023")
        assert "not evidence of no flood risk" in text


def test_refreshed_flood_evidence_updates_policy_deterministically():
    before = pd.DataFrame(
        [policy_cell(), policy_cell(flood_years_ge3_area_fraction=0.2, flood_area_fraction=0.2)]
    )
    after = before.copy()
    after.loc[0, ["flood_years_ge3_area_fraction", "flood_area_fraction", "flood_distance_m"]] = [
        0.6,
        0.6,
        0.0,
    ]
    after.loc[1, ["flood_years_ge3_area_fraction", "flood_area_fraction", "flood_distance_m"]] = [
        0.0,
        0.0,
        4000.0,
    ]
    r1 = apply_policy(after, PCFG, "BALANCED")
    r2 = apply_policy(after.copy(), PCFG, "BALANCED")
    assert r1.equals(r2)
    assert list(r1["regional_search_status"]) == [
        "REGIONAL_DEPRIORITIZE",
        "NO_MAJOR_CONCERN_DETECTED",
    ]
    assert list(apply_policy(before, PCFG, "BALANCED")["regional_search_status"]) == [
        "NO_MAJOR_CONCERN_DETECTED",
        "STRONG_REGIONAL_CONCERN",
    ]


@pytest.mark.parametrize("frac", [0.0, 0.03, 0.07, 0.15, 0.3, 0.6, 0.9])
def test_profiles_remain_monotonic_on_refreshed_flood_schema(frac):
    rank = {
        "NO_MAJOR_CONCERN_DETECTED": 0,
        "REQUIRES_VERIFICATION": 1,
        "STRONG_REGIONAL_CONCERN": 2,
        "REGIONAL_DEPRIORITIZE": 3,
    }
    c = policy_cell(
        flood_years_ge3_area_fraction=frac,
        flood_area_fraction=frac,
        flood_distance_m=0.0 if frac else 300.0,
    )
    lv = [
        rank[apply_policy(pd.DataFrame([c]), PCFG, p)["regional_search_status"].iloc[0]]
        for p in PROFILES
    ]
    assert lv[0] >= lv[1] >= lv[2]


def test_min_years_cannot_exceed_record_length():
    raw = copy.deepcopy(yaml.safe_load((CONFIG_DIR / "hazard-policy.yaml").read_text("utf-8")))
    raw["source_requirements"]["flood"]["record_years"] = 2
    with pytest.raises(ValidationError, match="record length"):
        HazardPolicyConfig.model_validate(raw)
    hraw = copy.deepcopy(yaml.safe_load((CONFIG_DIR / "hazard.yaml").read_text("utf-8")))
    hraw["flood"]["legacy_source"]["used_for_interpretation"] = True
    with pytest.raises(ValidationError, match="legacy"):
        HazardConfig.model_validate(hraw)


def test_provenance_like_records_carry_no_credential(monkeypatch):
    """Anything serialised from an acquisition context must not contain the value."""
    monkeypatch.setenv("HM_TEST_KEY", FAKE)
    s = load_secret("HM_TEST_KEY", env_file=None)
    record = {
        "access_method": "authenticated GISTDA API",
        "credential_source": "environment",
        "url": sanitize_url(f"https://x.test/f?api_key={s.reveal()}"),
        "secret": repr(s),
    }
    assert FAKE not in json.dumps(record)
