# ruff: noqa: E501
"""Manual-import contract for sources an agent cannot fetch (MOE register workbook, MoPH HCODE export).

A manually supplied file receives the SAME provenance as an automated download: a manifest naming the publisher,
dataset, original URL, download date, file name, SHA-256, licence and who/what acquired it. The original file is never
edited. Nothing is trusted because it came from an official website: schema, ids, coordinates, provinces, dates and
coverage are all checked, and a file that fails a blocking check is refused (fail closed).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from hearthmap.ingestion.secrets import is_sanitized

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REQUIRED_MANIFEST_FIELDS = (
    "publisher",
    "dataset_title",
    "original_download_url",
    "download_date",
    "file_name",
    "file_sha256",
    "licence",
    "acquired_by",
)


class ManualManifestError(ValueError):
    """The manual manifest is incomplete, inconsistent with the file, or carries a credential."""


class UnexpectedSchemaError(ValueError):
    """The supplied table does not contain the fields the importer needs; nothing is guessed."""


class ManualManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publisher: str
    dataset_title: str
    original_download_url: str
    download_date: dt.date
    file_name: str
    file_sha256: str
    licence: str
    acquired_by: str  # the person or tool that obtained the file (a name/role, never a credential)
    notes: str | None = None

    @field_validator("file_sha256")
    @classmethod
    def _sha(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", v.lower()):
            raise ValueError("file_sha256 must be 64 hex characters")
        return v.lower()

    @field_validator("original_download_url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not is_sanitized(v):
            raise ValueError("original_download_url carries a credential; record the sanitised URL")
        return v

    @field_validator("publisher", "dataset_title", "licence", "acquired_by", "file_name")
    @classmethod
    def _nonblank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> ManualManifest:
    data = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    missing = [f for f in REQUIRED_MANIFEST_FIELDS if not data.get(f)]
    if missing:
        raise ManualManifestError(f"manifest {path} is missing {missing}")
    return ManualManifest(**{k: v for k, v in data.items() if k in ManualManifest.model_fields})


def verify_manual_file(manifest: ManualManifest, directory: Path) -> Path:
    """The file named in the manifest must exist and match its recorded SHA-256 (the original, untouched)."""
    f = Path(directory) / manifest.file_name
    if not f.exists():
        raise ManualManifestError(f"{f} not found")
    actual = sha256_file(f)
    if actual != manifest.file_sha256:
        raise ManualManifestError(
            f"SHA-256 mismatch for {f.name}: manifest {manifest.file_sha256[:12]}..., file {actual[:12]}..."
        )
    return f


# -- reading -------------------------------------------------------------------------------------------
def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path: Path, sheet: int = 0) -> pd.DataFrame:
    """Minimal .xlsx reader (zip + XML; no external dependency). First row is the header; values are strings/numbers."""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t"))
                for si in root.findall("m:si", NS)
            ]
        sheets = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        if not sheets:
            raise UnexpectedSchemaError(f"{path} has no worksheets")
        root = ET.fromstring(z.read(sheets[sheet]))
        rows: list[dict[int, Any]] = []
        for r in root.iter(f"{{{NS['m']}}}row"):
            cells: dict[int, Any] = {}
            for c in r.findall("m:c", NS):
                t = c.get("t")
                v = c.find("m:v", NS)
                if t == "inlineStr":
                    val: Any = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                elif v is None or v.text is None:
                    continue
                elif t == "s":
                    val = shared[int(v.text)]
                elif t in ("str", "b", "e"):
                    val = v.text
                else:
                    try:
                        val = float(v.text)
                        val = int(val) if val.is_integer() else val
                    except ValueError:
                        val = v.text
                cells[_col_index(c.get("r"))] = val
            rows.append(cells)
    if not rows:
        return pd.DataFrame()
    width = max((max(r) for r in rows if r), default=-1) + 1
    grid = [[r.get(i) for i in range(width)] for r in rows]
    header = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(grid[0])]
    return pd.DataFrame(grid[1:], columns=header)


def read_table(path: Path) -> pd.DataFrame:
    suf = Path(path).suffix.lower()
    if suf == ".xlsx":
        return read_xlsx(path)
    if suf == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    raise UnexpectedSchemaError(f"unsupported manual file type {suf!r} (supported: .xlsx, .csv)")


# -- schema -------------------------------------------------------------------------------------------
def load_import_config(path: Path = Path("config/manual-imports.yaml")) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text("utf-8"))


def map_schema(columns: list[str], spec: dict[str, Any]) -> dict[str, str | None]:
    """Logical field -> actual column by exact (case/space-insensitive) alias match. Required fields must resolve."""
    norm = {re.sub(r"\s+", "", str(c)).lower(): c for c in columns}
    found: dict[str, str | None] = {}
    for logical, aliases in spec["fields"].items():
        hit = next(
            (
                norm[re.sub(r"\s+", "", a).lower()]
                for a in aliases
                if re.sub(r"\s+", "", a).lower() in norm
            ),
            None,
        )
        found[logical] = hit
    missing = [f for f in spec["required"] if not found.get(f)]
    if missing:
        raise UnexpectedSchemaError(
            f"required fields not found: {missing}. Columns present: {list(columns)[:40]}"
        )
    return found


# -- QA -----------------------------------------------------------------------------------------------
def qa_manual_table(
    df: pd.DataFrame, cols: dict[str, str | None], spec: dict[str, Any], *, province_of: Any = None, today: dt.date | None = None,
) -> dict[str, Any]:  # fmt: skip
    """Blocking and advisory checks; returns a report. ``province_of(lon, lat) -> pcode|None`` is optional."""
    q = spec["qa"]
    today = today or dt.date.today()
    rep: dict[str, Any] = {"records": len(df), "blocking": [], "advisory": []}
    idc, loc, lac = cols["id"], cols["lon"], cols["lat"]
    ids = df[idc].astype(str).str.strip()
    dup = ids[ids.duplicated(keep=False) & ids.ne("")]
    rep["duplicate_official_ids"] = int(dup.nunique())
    if len(dup):
        rep["blocking"].append(f"{dup.nunique()} duplicate official ids")
    rep["missing_ids"] = int((ids == "").sum() + df[idc].isna().sum())
    lon = pd.to_numeric(df[loc], errors="coerce")
    lat = pd.to_numeric(df[lac], errors="coerce")
    miss = lon.isna() | lat.isna()
    rep["missing_coordinates"] = int(miss.sum())
    x0, y0, x1, y1 = q["thailand_bbox"]
    bad = ~miss & ~((lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1))
    rep["invalid_coordinates"] = int(bad.sum())
    rep["coordinate_coverage_pct"] = round(100 * float((~miss).mean()), 1) if len(df) else 0.0
    if len(df) and rep["coordinate_coverage_pct"] < q["min_coordinate_coverage_pct"]:
        rep["advisory"].append(
            f"coordinate coverage {rep['coordinate_coverage_pct']}% below {q['min_coordinate_coverage_pct']}%"
        )
    if len(df) and bad.mean() > q["max_invalid_coordinate_share"]:
        rep["blocking"].append(
            f"{int(bad.sum())} invalid coordinates (> {q['max_invalid_coordinate_share']:.0%})"
        )
    pc = cols.get("province")
    rep["province_mismatch"] = 0
    if province_of is not None and pc:
        stated = df[pc].astype(str).str.strip()
        actual = [
            province_of(a, b) if pd.notna(a) and pd.notna(b) else None
            for a, b in zip(lon, lat, strict=True)
        ]
        mism = [
            bool(a and s in q["aoi_province_names"] and a != q["aoi_province_names"][s])
            for a, s in zip(actual, stated, strict=True)
        ]
        rep["province_mismatch"] = int(sum(mism))
        if rep["province_mismatch"]:
            rep["advisory"].append(
                f"{rep['province_mismatch']} records whose coordinates fall outside their stated AOI province"
            )
    # stale internal dates
    dc = cols.get("updated")
    rep["latest_internal_date"] = None
    if dc:
        raw = df[dc]
        yrs = pd.to_numeric(raw, errors="coerce")
        if (
            yrs.notna().mean() > 0.5 and yrs.dropna().between(2400, 2700).all()
        ):  # Buddhist-era year (academic year) -> 31 Dec of the Gregorian year
            d = pd.to_datetime(
                (yrs - 543).dropna().astype(int).astype(str) + "-12-31", errors="coerce"
            )
        else:
            d = pd.to_datetime(raw, errors="coerce", dayfirst=True)
        if d.notna().any():
            latest = d.max().date()
            rep["latest_internal_date"] = latest.isoformat()
            rep["age_years"] = round((today - latest).days / 365.25, 2)
            if rep["age_years"] > q["stale_after_years"]:
                rep["blocking"].append(
                    f"newest internal date {latest} is {rep['age_years']} years old (> {q['stale_after_years']}); the file is not current"
                )
    else:
        rep["advisory"].append(
            "no internal update date column: the vintage cannot be verified from the data"
        )
    # coverage
    prov_col = cols.get("province")
    if prov_col:
        names = df[prov_col].astype(str).str.strip()
        n_aoi = int(names.isin(list(q["aoi_province_names"])).sum())
        rep["records_in_aoi_by_stated_province"] = n_aoi
        rep["distinct_provinces"] = int(names.nunique())
        if (
            len(df) >= q["national_min_records"]
            and rep["distinct_provinces"] < q["national_min_provinces"]
        ):
            rep["advisory"].append("file is large but covers few provinces")
        if n_aoi < q["aoi_min_records"]:
            rep["blocking"].append(
                f"only {n_aoi} AOI records (< {q['aoi_min_records']}): unexpected coverage"
            )
    rep["ok"] = not rep["blocking"]
    return rep
