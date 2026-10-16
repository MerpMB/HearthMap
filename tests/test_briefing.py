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
PUBLISH = ROOT / "scripts/briefing/publish_plates.py"
ASSETS = ROOT / "docs/product/hearthmap-briefing-v0.1/assets"
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


def _table_rows(section: str) -> list[str]:
    return [r for r in section.splitlines() if r.startswith("| ") and "---" not in r][1:]


def test_no_map_title_or_reference_area_implies_suitability():
    alts = re.findall(r"!\[([^\]]*)\]", TEXT)
    assert len(alts) == 12
    for alt in alts:
        assert not re.search(r"suitab|best|score|rank|recommend|เหมาะสม|ดีที่สุด|แนะนำ", alt, re.I), alt
    main = TEXT.split("## 16. ")[1].split("## ภาคผนวก")[0]
    full = TEXT.split("### F. ")[1].split("### G. ")[0]
    assert 8 <= len(_table_rows(main)) <= 10 and len(_table_rows(full)) == 13
    for section in (main, full):
        # the non-ranking disclaimer sits with each table, not on a page of its own
        assert "BEST / GOOD / BAD / RECOMMENDED" in section.split("|", 1)[0]
        for r in _table_rows(section):
            assert not re.search(r"\b(BEST|GOOD|BAD|RECOMMENDED|WORST)\b", r), r
            assert "candidate zone" not in r.lower()


def test_peacefulness_is_never_presented_as_directly_proxied():
    assert "ความหนาแน่นประชากรแทน" not in TEXT
    assert "แต่ไม่ใช่ความสงบเอง" in TEXT
    assert "population intensity ≠ built form ≠ peacefulness" in TEXT


def test_cover_is_presentation_first_and_states_draft_and_scoring():
    cover = TEXT.split("<!-- /cover -->")[0]
    assert "DRAFT · SCORING OFF · 16 OCT 2026" in cover
    assert "ภาพรวมข้อมูลพื้นที่และสิ่งที่เราเข้าใจได้แล้ว" in cover
    assert "Chiang Mai · Chiang Rai · Phayao" in cover
    for implementation_detail in ("1e21a14", "outputs/", "scripts/", "canonical", "render"):
        assert implementation_detail not in cover, implementation_detail
    colophon = TEXT.split("### H. Colophon")[1]
    for moved in ("1e21a14", "publish_plates.py", "make_plates.py", "render_html.py", "canonical"):
        assert moved in colophon, moved


def test_trust_boundary_is_one_two_column_page_and_keeps_all_items():
    sec = TEXT.split("## 13. ")[1].split("## 14. ")[0]
    assert "<!-- columns -->" in sec and "This boundary is intentional." in sec
    can = sec.split("WHAT WE CAN SEE NOW")[1].split("WHAT WE CANNOT CLAIM YET")[0]
    cannot = sec.split("WHAT WE CANNOT CLAIM YET")[1]
    assert can.count("\n- ") == 7 and cannot.count("\n- ") == 12


def test_layout_markers_are_balanced():
    assert TEXT.count("<!-- landscape -->") == TEXT.count("<!-- /landscape -->")
    assert len(re.findall(r"<!-- grid \w+ -->", TEXT)) == TEXT.count("<!-- /grid -->")
    assert TEXT.count("<!-- columns -->") == TEXT.count("<!-- /columns -->") == 1
    assert TEXT.count("<!-- cover -->") == TEXT.count("<!-- /cover -->") == 1


def test_evidence_family_matrix_covers_every_requirement_once():
    pytest.importorskip("matplotlib")
    mod = _load(PLATES, "briefing_make_plates_families")
    plan = yaml.safe_load((ROOT / "config/family-evaluability.yaml").read_text("utf-8"))
    ids = sorted(e["id"] for e in plan["entries"] if not e["id"].startswith("IRR-"))
    grouped = [i for _, _, members in mod.EVIDENCE_FAMILIES if members for i in members]
    assert sorted(grouped) == ids
    families = {en for _, en, _ in mod.EVIDENCE_FAMILIES}
    for want in ("Hazard", "Education", "Healthcare", "Town services", "Land price", "Water"):
        assert want in families, want


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


def test_every_referenced_plate_is_generated_published_and_tracked_safely():
    src = PLATES.read_text("utf-8")
    saved = set(re.findall(r'save\(fig, "([^"]+)"', src))
    links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", TEXT)
    assert links and all(link.startswith("hearthmap-briefing-v0.1/assets/") for link in links)
    referenced = {Path(link).stem for link in links}
    published = set(_load(PUBLISH, "briefing_publish_plates").PUBLISHED)
    assert referenced == published and published <= saved
    files = {p.stem: p for p in ASSETS.glob("*")}
    assert set(files) == published  # only the curated plates, nothing else
    for p in files.values():
        assert p.suffix == ".png" and p.stat().st_size <= 1_000_000, p.name
    assert "outputs/briefing/maps" not in "".join(links)
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
