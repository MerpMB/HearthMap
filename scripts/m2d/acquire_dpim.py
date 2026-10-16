# ruff: noqa: E501
"""M2D: acquire DPIM (Department of Primary Industries and Mines) mining-concession context.

CURRENT: the official public open API (open.dpim.go.th/public/openapi/concession/search, no key), 879 current concession records nationally.
  It carries province, area (rai/ngan/wa), dates and status flags; NO coordinates and NO tambon. Holder names/tax ids/customer ids are personal data
  that this project does not need: they are removed BEFORE the file is written (documented transformation, listed in the manifest).
LEGACY: the data.go.th 2016-06-21 concession snapshot (TIS-620 CSV, tambon level, no coordinates). LEGACY_CONTEXT only; never current truth.
Neither source locates a pit, a quarry or a stone-crushing plant. They cannot support a distance or exclusion claim.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir, register_existing

VERSION = "dpim-api-2026-10-16"
API = "https://open.dpim.go.th/public/openapi/concession/search"
LEGACY = "https://data.go.th/dataset/b9da4f6d-fb97-4db7-895f-512d9df9df8c/resource/b991ef39-9282-4926-ae04-500163dc94f9/download/21392016100621dpim200.csv"
PII = ("name", "tax_no", "customer_id")
UA = {"User-Agent": "Mozilla/5.0 HearthMap/0.1 (local research)"}


def main() -> int:
    d = raw_dir(Path("data"), "mining-dpim-concessions", VERSION)
    if (d / "manifest.json").exists():
        print("already acquired")
        return 0
    d.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(API, headers=UA), timeout=180) as r:
        payload = json.loads(r.read())
    rows = payload["detail"]["data"]
    for row in rows:
        for k in PII:
            row.pop(k, None)
    target = d / "concession_search_current.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
    arts = [
        register_existing(target, source_url=API, acquired_at=datetime.now(UTC)),
        download(LEGACY, d, filename="concession_2016-06-21_legacy.csv"),
    ]
    RawManifest(
        source_id="mining-dpim-concessions",
        version=VERSION,
        landing_page="https://catalog.dpim.go.th/dataset/mineralroyaltypayer",
        licence="current API: Creative Commons Attribution Share-Alike (catalogue); legacy snapshot: Creative Commons Attributions (data.go.th)",
        publisher_metadata={
            "current_records": len(rows),
            "removed_fields_before_storage": list(PII),
            "removal_reason": "personal data not needed for area-level context",
            "current_fields": sorted(rows[0]),
            "legacy_snapshot_date": "2016-06-21",
            "legacy_encoding": "TIS-620 (cp874), one title line before the header",
        },
        notes=[
            "Neither source has coordinates: province (current) or tambon (legacy) is the finest location.",
            "Legacy snapshot is LEGACY_CONTEXT, not current truth.",
        ],
        artifacts=arts,
    ).write(d)
    print("acquired", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
