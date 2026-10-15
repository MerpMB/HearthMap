# ruff: noqa: E501
"""Source roles and current-vs-legacy facility reconciliation (M2A.1).

A facility layer has exactly one PRIMARY source. Validation / historical / classification sources never
add rows to it silently: they are compared (MATCHED / CURRENT_ONLY / LEGACY_ONLY / POSSIBLE_MATCH / CONFLICT)
with the evidence for each decision retained. Nothing here merges stale and current records into current truth.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely

ROLES = (
    "PRIMARY",
    "AUTHORITATIVE_CLASSIFICATION",
    "HISTORICAL_VALIDATION",
    "CURRENT_VALIDATION",
    "FALLBACK",
)
STATUSES = ("MATCHED", "CURRENT_ONLY", "LEGACY_ONLY", "POSSIBLE_MATCH", "CONFLICT")


@dataclass(frozen=True)
class FacilitySource:
    name: str
    vintage_year: int  # Gregorian year of the data
    role: str
    current: bool  # True only for data considered current at verification time

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"unknown role {self.role}")


def compose_primary(
    primary: pd.DataFrame,
    primary_source: FacilitySource,
    others: dict[str, tuple[pd.DataFrame, FacilitySource]],
) -> pd.DataFrame:
    """Return the primary layer with provenance columns. Rows of other sources are NEVER appended.

    Mixing is refused: a stale source cannot be labelled PRIMARY while a current one exists among ``others``.
    """
    if primary_source.role not in ("PRIMARY", "FALLBACK"):
        raise ValueError(
            "the layer source must have role PRIMARY (or FALLBACK when no current primary is reachable)"
        )
    for name, (_, src) in others.items():
        if src.role in ("PRIMARY", "FALLBACK"):
            raise ValueError(
                f"{name}: a second PRIMARY/FALLBACK source would silently mix stale and current records"
            )
        if src.current and not primary_source.current and src.role == "PRIMARY":
            raise ValueError("a current source must not be demoted behind a stale primary")
    out = primary.copy()
    out["primary_source"] = primary_source.name
    out["primary_source_role"] = primary_source.role
    out["primary_source_vintage_year"] = primary_source.vintage_year
    out["primary_source_current"] = primary_source.current
    return out


_PREFIX = re.compile(r"^(โรงเรียน|รร\.|ร\.ร\.|ศูนย์พัฒนาเด็กเล็ก|ศพด\.|วิทยาลัย)")


def comparison_name(name: str) -> str:
    """Name key for comparing registers: NFC, no spaces/zero-width, no generic institution prefix."""
    n = unicodedata.normalize("NFC", str(name or ""))
    n = "".join(ch for ch in n if ch not in "​‌‍﻿")
    n = re.sub(r"\s+", "", n)
    return _PREFIX.sub("", n)


_HEALTH_PREFIX = re.compile(r"^(โรงพยาบาลส่งเสริมสุขภาพตำบล|รพ\.?สต\.?|โรงพยาบาล|ศูนย์สุขภาพชุมชน|คลินิก)")
_HEALTH_SUFFIX = re.compile(r"(จังหวัด|จ\.|ตำบล|ต\.|อำเภอ|อ\.).*$")


def health_comparison_name(name: str) -> str:
    """Health-facility name key: drops the unit-type prefix and any trailing province/district/sub-district words."""
    n = unicodedata.normalize("NFC", str(name or ""))
    n = "".join(ch for ch in n if ch not in "​‌‍﻿")
    n = re.sub(r"^(กรมการแพทย์|กรมสุขภาพจิต)", "", re.sub(r"\s+", " ", n).strip()).strip()
    n = n.split(" จังหวัด")[0].split(" ตำบล")[0].split(" อำเภอ")[0].replace(" ", "")
    n = _HEALTH_PREFIX.sub("", n)
    return n


def reconcile(
    current: pd.DataFrame, legacy: pd.DataFrame, *, match_radius_m: float = 300.0, conflict_m: float = 500.0, possible_radius_m: float = 150.0, same_name_far_m: float = 3000.0, name_fn=None,
    id_col_current: str | None = None, id_col_legacy: str | None = None,
) -> pd.DataFrame:  # fmt: skip
    """Compare two sources. Both frames need ``name``, ``x``, ``y`` (metres) and a unique ``rec_id``.

    Order of evidence: (1) identical official id; (2) identical comparison name within ``match_radius_m`` => MATCHED;
    (3) identical comparison name farther than ``conflict_m`` but within ``same_name_far_m`` => CONFLICT (beyond that it is treated as a different school with a common name); (4) a different name within
    ``possible_radius_m`` => POSSIBLE_MATCH; otherwise CURRENT_ONLY / LEGACY_ONLY. Every row keeps its evidence.
    The first argument is the more recent / reference source; "legacy" is the one compared against it.
    """
    name_fn = name_fn or comparison_name
    cur = current.reset_index(drop=True).copy()
    leg = legacy.reset_index(drop=True).copy()
    cur["_k"] = cur["name"].map(name_fn)
    leg["_k"] = leg["name"].map(name_fn)
    leg_by_key: dict[str, list[int]] = {}
    for j, k in enumerate(leg["_k"]):
        leg_by_key.setdefault(k, []).append(j)
    leg_by_id: dict[str, int] = {}
    if id_col_current and id_col_legacy:
        leg_by_id = {
            str(v): j for j, v in enumerate(leg[id_col_legacy]) if str(v) not in ("", "nan", "None")
        }
    lt = shapely.STRtree(shapely.points(leg[["x", "y"]].to_numpy(float))) if len(leg) else None
    rows = []
    used_leg: dict[int, int] = {}
    for _, r in cur.iterrows():
        status, evidence, j_match, dist = "CURRENT_ONLY", "NO_COUNTERPART", None, np.nan
        cid = str(r[id_col_current]) if id_col_current else ""
        if cid in leg_by_id:
            j = leg_by_id[cid]
            d = float(np.hypot(r["x"] - leg.at[j, "x"], r["y"] - leg.at[j, "y"]))
            status, evidence, j_match, dist = (
                ("MATCHED" if d <= conflict_m else "CONFLICT"),
                "OFFICIAL_ID",
                j,
                d,
            )
        else:
            cands = [
                (float(np.hypot(r["x"] - leg.at[j, "x"], r["y"] - leg.at[j, "y"])), j)
                for j in leg_by_key.get(r["_k"], [])
                if r["_k"]
            ]
            cands = sorted(
                c for c in cands if c[0] <= same_name_far_m
            )  # a same-name school farther away is a different school
            if cands and cands[0][0] <= match_radius_m:
                status, evidence, j_match, dist = (
                    "MATCHED",
                    "IDENTICAL_NAME_WITHIN_RADIUS",
                    cands[0][1],
                    cands[0][0],
                )
            elif cands:
                status, evidence, j_match, dist = (
                    "CONFLICT",
                    "IDENTICAL_NAME_COORDINATES_DISAGREE",
                    cands[0][1],
                    cands[0][0],
                )
            elif lt is not None:
                near = lt.query(shapely.points(r["x"], r["y"]).buffer(possible_radius_m))
                near = [int(j) for j in near if leg.at[j, "_k"] != r["_k"]]
                if near:
                    j = min(
                        near,
                        key=lambda j: np.hypot(r["x"] - leg.at[j, "x"], r["y"] - leg.at[j, "y"]),
                    )
                    status, evidence, j_match = (
                        "POSSIBLE_MATCH",
                        "DIFFERENT_NAME_NEARBY_NOT_MERGED",
                        j,
                    )
                    dist = float(np.hypot(r["x"] - leg.at[j, "x"], r["y"] - leg.at[j, "y"]))
        if j_match is not None and status in ("MATCHED", "CONFLICT"):
            used_leg[j_match] = used_leg.get(j_match, 0) + 1
        rows.append(
            {
                "rec_id": r["rec_id"],
                "name": r["name"],
                "status": status,
                "evidence": evidence,
                "counterpart_rec_id": leg.at[j_match, "rec_id"] if j_match is not None else None,
                "counterpart_name": leg.at[j_match, "name"] if j_match is not None else None,
                "distance_m": dist,
                "side": "current_side",
            }
        )
    for j, r in leg.iterrows():
        if j not in used_leg:
            possible = any(
                x["status"] == "POSSIBLE_MATCH" and x["counterpart_rec_id"] == r["rec_id"]
                for x in rows
            )
            rows.append(
                {
                    "rec_id": r["rec_id"],
                    "name": r["name"],
                    "status": "POSSIBLE_MATCH" if possible else "LEGACY_ONLY",
                    "evidence": "DIFFERENT_NAME_NEARBY_NOT_MERGED"
                    if possible
                    else "NO_COUNTERPART",
                    "counterpart_rec_id": None,
                    "counterpart_name": None,
                    "distance_m": np.nan,
                    "side": "legacy_side",
                }
            )
    return pd.DataFrame(rows)


def summarise(rec: pd.DataFrame) -> dict[str, float]:
    cs = rec[rec["side"] == "current_side"]
    n = len(cs)
    out = {f"current_side_{s.lower()}": int((cs["status"] == s).sum()) for s in STATUSES}
    out["current_side_records"] = n
    out["legacy_side_only"] = int(
        ((rec["side"] == "legacy_side") & (rec["status"] == "LEGACY_ONLY")).sum()
    )
    out["match_rate_pct"] = round(100 * out["current_side_matched"] / n, 1) if n else 0.0
    return out
