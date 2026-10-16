# ruff: noqa: E501
"""M2C: validate the evaluability plan and write the permission matrix and the two generated documents.

Outputs: outputs/m2c/evaluation-permission-matrix.csv (planning artifact, no score columns),
docs/research/m2c-evidence-backlog.md, docs/product/m2c-evaluability-plan.md. Nothing is evaluated or acquired.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from hearthmap.family.evaluability import (
    EvaluabilityError,
    check_plan,
    entry_priorities,
    load_backlog,
    load_plan,
    permission_rows,
    render_backlog_md,
    render_plan_md,
)
from hearthmap.family.requirements import check_requirements, load_requirements

OUT = Path("outputs/m2c")


def main() -> int:
    req = load_requirements()
    check_requirements(req)
    plan, backlog = load_plan(), load_backlog()
    try:
        check_plan(plan, req, backlog)
    except EvaluabilityError as e:
        print("EVALUABILITY PLAN INVALID:", e)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    rows = permission_rows(plan, req)
    pd.DataFrame(rows).to_csv(
        OUT / "evaluation-permission-matrix.csv", index=False, encoding="utf-8-sig"
    )
    Path("docs/research/m2c-evidence-backlog.md").write_text(
        render_backlog_md(plan, backlog, req), "utf-8"
    )
    Path("docs/product/m2c-evaluability-plan.md").write_text(
        render_plan_md(plan, backlog, req), "utf-8"
    )
    pr = entry_priorities(plan, req)
    print(
        f"{len(rows)} rows ({len(plan['entries'])} entries x 4 stages); FAMILY_SCORING_ALLOWED=False"
    )
    for p in (
        "P0",
        "P1",
        "P2",
        "P3",
        "NO_EVIDENCE_GAP",
        "NOT_PRIORITISED_REQUIREMENT_UNSET",
        "NOT_APPLICABLE_IRRELEVANT",
    ):
        print(p, [k for k, v in pr.items() if v == p])
    return 0


if __name__ == "__main__":
    sys.exit(main())
