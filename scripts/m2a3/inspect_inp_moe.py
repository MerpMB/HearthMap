# ruff: noqa: E501
"""M2A.3: inspect (not scrape) the MOE e-INSPECTION "basic info" page and its Data Virtualization reports.

What it does, once and politely: GET the HTML page, list the resource/endpoint URLs that are discoverable in the HTML,
and call the page's own metadata endpoint for the three listed reports. It does NOT query Power BI's internal query service,
does NOT read rendered tables, and does NOT touch any authenticated area. The Power BI observation recorded below was made by
viewing the public embed once in the in-app browser (as a person would); it is stored as notes, not as data.
Output: outputs/m2a3-review/inp-moe-inspection.json
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PAGE = "https://inp.moe.go.th/inspec2026/?module=basic_info"
META = "https://inp.moe.go.th/inspec2026/_pages/_api/get_powerbi_data.php?id={i}"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}
OUT = Path("outputs/m2a3-review")

OBSERVED_IN_BROWSER = {
    "method": "Public Power BI 'publish to web' embed opened once in the in-app browser; visible text only (no API calls made, no export attempted)",
    "observed_on": "2026-10-16",
    "report_1_title": "ข้อมูลนักเรียน จำแนกรายสถานศึกษาและหน่วยงานต้นสังกัด",
    "visible_filters": [
        "ปีการศึกษา (academic year)",
        "ภาคเรียนที่ (term)",
        "รหัส (school code)",
        "ค้นหาสถานศึกษา (school search)",
        "หน่วยงานต้นสังกัด (affiliation)",
        "ขนาดสถานศึกษา (size class)",
        "จังหวัด (province)",
        "อำเภอ (district)",
        "สัญชาติ (nationality)",
    ],
    "visible_school_table_columns": [
        "รหัสสถานศึกษา (10-digit MOE code)",
        "สภานศึกษา (school name)",
        "ขนาดสถานศึกษา (size class)",
        "เพศชาย",
        "เพศหญิง",
        "จำนวนรวม",
    ],
    "academic_year_term_shown": "2569 / term 1",
    "national_student_total_shown": 11508493,
    "fields_NOT_seen": [
        "latitude",
        "longitude",
        "education level / grades served",
        "school status",
        "district/subdistrict as a column",
        "any export or download control",
    ],
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(PAGE, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
        status = r.status
    urls = sorted(set(re.findall(r'(?:src|href|action)="(https?://[^"#]+)"', html)))
    ajax = re.findall(r"url:\s*'([^']+)'", html)
    iframes = re.findall(r'<iframe[^>]*src="(https?://[^"]+)"', html)
    reports = []
    for i in (1, 2, 3):
        req = urllib.request.Request(META.format(i=i), headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())["data"]
        reports.append(
            {
                "id": i,
                "title": d["basic_title"],
                "footer_source": d["basic_footer"],
                "embed_host": re.match(r"https://([^/]+)/", d["powerbi_link"]).group(1),
                "embed_kind": "Power BI publish-to-web (report key in URL, not recorded here)",
                "page_record_updated": d["updated_at"],
            }
        )
        # the embed key is a capability URL: kept out of the repository and out of this file
    out = {
        "checked": datetime.now(UTC).isoformat(),
        "publisher": "Ministry of Education, Office of the Inspector General (e-INSPECTION), data from the MOE Data Virtualization service",
        "host": "inp.moe.go.th",
        "page": PAGE,
        "http_status": status,
        "access_method": "HTML page that embeds Power BI reports; its own endpoint get_powerbi_data.php?id=N returns report metadata and the embed link",
        "parameters": {"module": "basic_info", "id": "1|2|3 (report selector)"},
        "discoverable_in_html": {
            "ajax_endpoints": ajax,
            "iframes_hosts": sorted({re.match(r"https://([^/]+)/", u).group(1) for u in iframes}),
            "document_pdfs": len(
                [u for u in re.findall(r'"(/inspec2026/documents/[^"]+\.pdf)"', html)]
            ),
            "external_links": [u for u in urls if "moe.go.th" in u or "203.159" in u][:12],
        },
        "documented_api": None,
        "export_control_in_html": None,
        "structured_endpoint": "NONE: data sits behind Power BI's internal query service, which is an undocumented interface and was NOT used",
        "reports": reports,
        "observed_in_browser": OBSERVED_IN_BROWSER,
        "licence_or_terms": "none stated on the page or on the report; not inferred from the parent site",
        "verdict": "SOURCE_VERIFIED as current institution-level PRESENCE evidence (school code, name, size, enrolment, affiliation, province/district filters, academic year 2569) but NOT_SUITABLE_AS_PRIMARY_LOCATION_REGISTER: no coordinates, no grades served, no status, no export",
    }
    (OUT / "inp-moe-inspection.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    print(
        json.dumps(
            {
                k: out[k]
                for k in ("http_status", "documented_api", "structured_endpoint", "verdict")
            },
            indent=1,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
