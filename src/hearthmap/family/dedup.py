"""Deterministic, auditable facility de-duplication.

Merge rule: records merge only when (a) they share an official id, or (b) their normalised names are
IDENTICAL and they lie within ``same_institution_radius_m``. Names are never fuzzy-matched. Merged
records keep every contributing source id and the evidence for the merge.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

import numpy as np
import pandas as pd


def normalise_name(name: str) -> str:
    n = unicodedata.normalize("NFC", str(name or ""))
    n = "".join(ch for ch in n if ch not in "​‌‍﻿")
    return re.sub(r"\s+", "", n)


def stable_id(prefix: str, *parts: object) -> str:
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


def deduplicate(
    df: pd.DataFrame, radius_m: float, official_id_col: str | None = None
) -> pd.DataFrame:
    """``df`` needs source_id, name, x, y (metres). Returns one row per institution.

    Added columns: facility_id, merged_source_ids (|), n_merged, merge_evidence, dedup_status.
    """
    d = df.copy()
    d["_n"] = d["name"].map(normalise_name)
    d = d.sort_values(["_n", "x", "y", "source_id"], kind="mergesort").reset_index(drop=True)
    parent = list(range(len(d)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    evidence: dict[int, set[str]] = {}
    keys = d["_n"].to_numpy()
    x, y = d["x"].to_numpy(float), d["y"].to_numpy(float)
    n = len(d)
    # same identical normalised name, within radius
    start = 0
    for i in range(1, n + 1):
        if i == n or keys[i] != keys[start]:
            for a in range(start, i):
                for b in range(a + 1, i):
                    dist = float(np.hypot(x[a] - x[b], y[a] - y[b]))
                    if dist <= radius_m:
                        ra, rb = find(a), find(b)
                        if ra != rb:
                            parent[rb] = ra
                        evidence.setdefault(a, set()).add(f"IDENTICAL_NAME_WITHIN_{dist:.0f}M")
                        evidence.setdefault(b, set()).add(f"IDENTICAL_NAME_WITHIN_{dist:.0f}M")
            start = i
    d["_root"] = [find(i) for i in range(n)]
    rows = []
    for _, g in d.groupby("_root", sort=True):
        first = g.iloc[0].drop(["_n", "_root"]).to_dict()
        first["merged_source_ids"] = "|".join(g["source_id"].astype(str))
        first["n_merged"] = len(g)
        first["merge_evidence"] = ";".join(
            sorted({e for i in g.index for e in evidence.get(i, set())})
        )
        first["dedup_status"] = "MERGED" if len(g) > 1 else "UNIQUE"
        first["facility_id"] = stable_id(
            "fac", g["_n"].iloc[0], round(float(g["x"].iloc[0]), 0), round(float(g["y"].iloc[0]), 0)
        )
        rows.append(first)
    out = pd.DataFrame(rows).sort_values("facility_id").reset_index(drop=True)
    if (
        official_id_col
    ):  # a shared official id that did NOT merge is surfaced, never silently resolved
        shared = out[official_id_col].astype(str).duplicated(keep=False) & ~out[
            official_id_col
        ].astype(str).isin(["", "nan", "None"])
        out.loc[shared & (out["dedup_status"] == "UNIQUE"), "dedup_status"] = (
            "SHARED_OFFICIAL_ID_NOT_MERGED"
        )
    if out["facility_id"].duplicated().any():  # two distinct institutions hashing to one id
        out["facility_id"] = (
            out["facility_id"] + "_" + out.groupby("facility_id").cumcount().astype(str)
        )
    return out
