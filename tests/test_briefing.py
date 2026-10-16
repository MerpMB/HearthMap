"""Briefing v0.1: no scoring language, current artifacts only, gates unchanged, review PENDING."""

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/product/hearthmap-briefing-v0.1.md"
PLATES = ROOT / "scripts/briefing/make_plates.py"
RENDER = ROOT / "scripts/briefing/render_html.py"
GATES = yaml.safe_load((ROOT / "config/human-qa.yaml").read_text("utf-8"))["gates"]
TEXT = DOC.read_text("utf-8")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_review_gate_is_pending_and_no_other_gate_changes():
    g = GATES["hearthmap_briefing_v0_1_review"]
    assert g["status"] == "PENDING" and g["review_date"] is None and g["result"] is None
    assert GATES["m2a_human_visual_signoff"]["status"] == "PENDING"
    assert GATES["m2d_human_visual_signoff"]["status"] == "PASSED"
    item = GATES["m2d_human_visual_signoff"]["visualization_backlog"][0]
    assert item["id"] == "M2A-EDU-LEGEND-ACCOUNTING" and item["status"] == "OPEN_NON_BLOCKING"
    plan = yaml.safe_load((ROOT / "config/family-evaluability.yaml").read_text("utf-8"))
    assert plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False


def test_briefing_states_the_gates_explicitly():
    for needle in (
        "HEARTHMAP_BRIEFING_V0_1_REVIEW = PENDING",
        "FAMILY_SCORING_ALLOWED = false",
        "M2D_HUMAN_VISUAL_SIGNOFF = PASSED",
        "M2A_HUMAN_VISUAL_SIGNOFF = PENDING",
        "NEITHER DEFINITION HAS BEEN SELECTED",
        "M2A-EDU-LEGEND-ACCOUNTING",
    ):
        assert needle in TEXT, needle


def test_no_map_title_or_reference_area_implies_suitability():
    alts = re.findall(r"!\[([^\]]*)\]", TEXT)
    assert len(alts) == 10
    for alt in alts:
        assert not re.search(r"suitab|best|score|rank|recommend|เหมาะสม|ดีที่สุด|แนะนำ", alt, re.I), alt
    section = TEXT.split("## 17.")[1].split("## ภาคผนวก")[0]
    rows = [r for r in section.splitlines() if r.startswith("| ") and "---" not in r][1:]
    assert len(rows) >= 11
    for r in rows:
        assert not re.search(r"\b(BEST|GOOD|BAD|RECOMMENDED|WORST)\b", r), r
        assert "candidate zone" not in r.lower()


def test_plates_read_only_current_corrected_artifacts():
    src = PLATES.read_text("utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
    code = code.split('"""', 2)[
        2
    ]  # drop the module docstring, which names the stale paths it avoids
    assert "outputs/m2a2-origin/family-infrastructure-evidence.parquet" in code
    for stale in (
        "outputs/m2a/",
        "outputs/m2a2/",
        "outputs/m2a-review",
        "outputs/m2a2-review",
        "m2e-story",
    ):
        assert stale not in code, stale
    assert "CANONICAL_AOI_ANALYSIS_POINT" in code


def test_every_referenced_plate_is_generated():
    src = PLATES.read_text("utf-8")
    saved = set(re.findall(r'save\(fig, "([^"]+)"\)', src))
    referenced = set(re.findall(r"outputs/briefing/maps/([^)]+)\.png", TEXT))
    assert referenced and referenced <= saved
    for required in (
        "00-hearthmap-overview",
        "01-hazard-foundation",
        "02-routing-accessibility",
        "03-education-healthcare",
        "04-settlement-built-form",
        "05-town-services",
        "06-industry-mining-context",
        "07-evidence-state",
        "08-future-product-concept",
    ):
        assert required in saved, required


def test_orientation_labels_cover_the_requested_reference_locations():
    pytest.importorskip("matplotlib")
    mod = _load(PLATES, "briefing_make_plates")
    names = {en for _, en in mod.PRIMARY_LABELS.values()}
    for want in (
        "Chiang Mai",
        "Chiang Rai",
        "Phayao",
        "Mae Sai",
        "Fang",
        "Mae Suai",
        "Wiang Pa Pao",
        "Pong",
        "Dok Kham Tai",
        "Chiang Kham",
        "Chiang Khong",
    ):
        assert want in names, want
    # every fallback coordinate belongs to a labelled district
    assert set(mod.FALLBACK_LONLAT) <= set(mod.PRIMARY_LABELS) | set(mod.SECONDARY_LABELS)


def test_renderer_converts_the_subset_without_markdown_dependency():
    mod = _load(RENDER, "briefing_render_html")
    html = mod.convert(
        "## T\n\n| a | b |\n|---|---|\n| **x** | `y` |\n\n"
        "```flow\nA — one ◀ อยู่ตรงนี้\nB — two\n```\n\n> q\n\n- i\n"
    )
    assert "<h2>T</h2>" in html and "<strong>x</strong>" in html and "<code>y</code>" in html
    assert html.count('class="step') == 2 and 'class="step now"' in html
    assert "<blockquote>" in html and "<li>i</li>" in html
    assert "import markdown" not in RENDER.read_text("utf-8")
