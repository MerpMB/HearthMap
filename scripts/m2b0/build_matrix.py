# ruff: noqa: E501
"""M2B.0: validate family requirements and write the requirement-evidence matrix.

Reads config/family-requirements.yaml (USER_REQUIREMENT) and config/family-evidence-capability.yaml (DATA_CAPABILITY).
Writes outputs/m2b0/requirement-evidence-matrix.csv. No grid cell is read, scored or ranked; no recommendation is produced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from hearthmap.family.requirements import (
    RequirementConflict,
    check_requirements,
    evidence_matrix,
    load_capability,
    load_requirements,
)

OUT = Path("outputs/m2b0")


def main() -> int:
    req = load_requirements()
    cap = load_capability()
    try:
        warnings = check_requirements(req)
    except RequirementConflict as e:
        print("REQUIREMENTS CONFLICT (nothing was normalised):", e)
        return 1
    rows = evidence_matrix(req, cap)
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "requirement-evidence-matrix.csv", index=False, encoding="utf-8-sig")
    print(f"{len(df)} rows; capability: {df['data_capability'].value_counts().to_dict()}")
    print(
        f"requirements still UNSET: {int(df['needs_user_input'].sum())} of {int((df['kind'] == 'USER_REQUIREMENT').sum())}"
    )
    print(f"warnings: {len(warnings)}; evaluation_rule: {df['evaluation_rule'].unique().tolist()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
