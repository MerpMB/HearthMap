# ruff: noqa: E501
"""M2B.0: write docs/product/family-requirements-v0.1-summary.md from the requirement and capability configs."""

from __future__ import annotations

import sys
from pathlib import Path

from hearthmap.family.requirements import (
    check_requirements,
    load_capability,
    load_requirements,
    render_summary,
)

OUT = Path("docs/product/family-requirements-v0.1-summary.md")


def main() -> int:
    req = load_requirements()
    check_requirements(req)
    OUT.write_text(render_summary(req, load_capability()), "utf-8")
    print("written", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
