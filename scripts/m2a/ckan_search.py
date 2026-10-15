"""M2A: search a CKAN catalogue (data.go.th, data.dmr.go.th, ...) and summarise datasets.

Read-only metadata inspection: title, organisation, dates, licence, access condition and the
resources (name, format, url). Used to verify catalogue records before any download.
"""

# ruff: noqa: E501

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 HearthMap research (local)"


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def main() -> int:
    base = sys.argv[1].rstrip("/")
    for q in sys.argv[2:]:
        url = f"{base}/api/3/action/package_search?q={urllib.parse.quote(q)}&rows=15"
        try:
            d = get(url)["result"]
        except Exception as e:
            print(f"## {q}: ERROR {e}")
            continue
        print(f"## {q}: {d['count']} datasets")
        for p in d["results"]:
            print(
                f"- {p['name']} | {p['title']} | org={(p.get('organization') or {}).get('title')} "
                f"| created={str(p.get('metadata_created'))[:10]} modified={str(p.get('metadata_modified'))[:10]} "
                f"| licence={p.get('license_title')} | cond={str(p.get('accessible_condition'))[:60]!r}"
            )
            print(f"    notes: {str(p.get('notes'))[:250]!r}")
            for r in p.get("resources", [])[:8]:
                print(f"    RES {r.get('name')} [{r.get('format')}] {str(r.get('url'))[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
