# ruff: noqa: E501, RUF001, N806
"""HearthMap Spatial Evidence Briefing v0.1 - presentation map plates (descriptive only, no scoring).

Every plate is drawn from the CURRENT corrected artifacts:
  * hazard actions        outputs/m1e/natural-hazard-actions.parquet
  * education/healthcare  outputs/m2a2-origin/family-infrastructure-evidence.parquet  (canonical AOI origins, M2D.1e)
  * regional context      outputs/m2d/regional-context-evidence.parquet
  * evidence states       config/family-evaluability.yaml
The historical M2A images (outputs/m2a-review, outputs/m2a, outputs/m2a2) are NOT read: they predate the origin correction.

No plate computes a score, rank, threshold, buffer or candidate zone. Colours describe one measured variable or one recorded
state each; no colour means "good". Output: outputs/briefing/maps/*.png and outputs/briefing/briefing-facts.json (git-ignored).

Usage:  python scripts/briefing/make_plates.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
import yaml
from matplotlib.colors import LightSource, LogNorm, PowerNorm, to_rgba
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle
from pyproj import Transformer

from hearthmap.context.settlement import GridIndex

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "briefing"
MAPS = OUT / "maps"
CRS = "EPSG:32647"
SNAPSHOT = "2026-10-16"

# Current corrected artifacts (see module docstring). Stale M2A paths are deliberately absent.
HAZARD = ROOT / "outputs/m1e/natural-hazard-actions.parquet"
FAMILY = ROOT / "outputs/m2a2-origin/family-infrastructure-evidence.parquet"
CONTEXT = ROOT / "outputs/m2d/regional-context-evidence.parquet"
TERRAIN = ROOT / "outputs/m1b/hazard-evidence.parquet"
BOUNDARIES = ROOT / "data/processed/m1a/boundaries.gpkg"
ROADS = ROOT / "data/processed/m1a/layers.gpkg"
DOPA = ROOT / "data/raw/places-dopa-gis02"
OCHA = ROOT / "data/raw/boundaries-ocha-cod-ab"
OSM_GEOM = ROOT / "data/processed/m2d/osm_industry_geometries.csv"
TAMBON_TABLE = ROOT / "outputs/m2d/tables/tambon-industry-mining-context.csv"
EVALUABILITY = ROOT / "config/family-evaluability.yaml"

# ---------------------------------------------------------------- visual language
FONT = ["Leelawadee UI", "Tahoma", "DejaVu Sans"]
PAPER = "#FAF8F3"
INK = "#2B2B2B"
MUTED = "#6E6A62"
PROV_EDGE = "#2F2F2F"
DIST_EDGE = "#9A958B"
NO_DATA = "#D3D0C8"  # unresolved: no connected road within 1 km
NO_ROUTE = "#9C958A"  # unresolved for another recorded reason (e.g. beyond the 120 min search)
plt.rcParams.update(
    {
        "font.family": FONT,
        "font.size": 9,
        "text.color": INK,
        "axes.edgecolor": MUTED,
        "figure.facecolor": PAPER,
        "savefig.facecolor": PAPER,
    }
)
NOT_A_SCORE = (
    "ข้อมูลเชิงพรรณนาเท่านั้น · ไม่ใช่คะแนน ไม่ใช่การจัดอันดับ ไม่ใช่คำแนะนำ · FAMILY_SCORING_ALLOWED = false"
)

# Reference locations: ORIENTATION LABELS ONLY, never candidate zones. Position = the DOPA GIS02 district-office point
# (ที่ว่าการอำเภอ) when it lies inside its own district; otherwise the M2D calibration reference-town coordinate.
PRIMARY_LABELS = {  # adm2_pcode -> (Thai, English)
    "TH5001": ("เชียงใหม่", "Chiang Mai"),
    "TH5701": ("เชียงราย", "Chiang Rai"),
    "TH5601": ("พะเยา", "Phayao"),
    "TH5709": ("แม่สาย", "Mae Sai"),
    "TH5009": ("ฝาง", "Fang"),
    "TH5710": ("แม่สรวย", "Mae Suai"),
    "TH5711": ("เวียงป่าเป้า", "Wiang Pa Pao"),
    "TH5606": ("ปง", "Pong"),
    "TH5605": ("ดอกคำใต้", "Dok Kham Tai"),
    "TH5603": ("เชียงคำ", "Chiang Kham"),
    "TH5703": ("เชียงของ", "Chiang Khong"),
}
SECONDARY_LABELS = {
    "TH5002": ("จอมทอง", "Chom Thong"),
    "TH5016": ("ฮอด", "Hot"),
    "TH5003": ("แม่แจ่ม", "Mae Chaem"),
    "TH5004": ("เชียงดาว", "Chiang Dao"),
    "TH5011": ("พร้าว", "Phrao"),
    "TH5018": ("อมก๋อย", "Omkoi"),
    "TH5705": ("พาน", "Phan"),
    "TH5704": ("เทิง", "Thoeng"),
    "TH5604": ("เชียงม่วน", "Chiang Muan"),
    "TH5607": ("แม่ใจ", "Mae Chai"),
}
LABEL_OFFSET = {  # metres, to keep neighbouring labels apart
    "TH5601": (-2500, 1200, "right"),
    "TH5605": (2000, -9000, "left"),
    "TH5701": (-2500, 2500, "right"),
    "TH5709": (-2500, -3000, "right"),
    "TH5703": (-2500, -9000, "right"),
    "TH5607": (2500, 1500, "left"),
}
FALLBACK_LONLAT = {  # M2D calibration reference towns (scripts/m2d/make_maps.py), used where DOPA has no usable office point
    "TH5001": (98.9853, 18.7883),
    "TH5701": (99.8310, 19.9072),
    "TH5601": (99.9019, 19.1664),
    "TH5009": (99.2139, 19.9167),
    "TH5709": (99.8783, 20.4276),
    "TH5703": (100.4097, 20.2605),
}


# ---------------------------------------------------------------- data
class Ctx:
    """Everything the plates share: grid index, rasters, boundaries and labels."""

    def __init__(self) -> None:
        ctx_cols = [
            "cell_id",
            "majority_pcode",
            "road_access_context",
            "population_worldpop2025_mass_aoi_clipped",
            "population_worldpop2025_intensity_per_nominal_grid_cell_km2",
            "built_ghsl2020_m2_aoi_clipped",
            "built_ghsl2020_intensity_fraction_of_nominal_grid_cell",
            "drive_time_to_nearest_service_cluster_core_min",
            "drive_time_to_nearest_service_cluster_broader_min",
            "service_cluster_core_definition_status",
            "service_cluster_broader_definition_status",
            *[f"drive_time_to_nearest_service_{c}_min" for c in SERVICE_COMPONENTS],
        ]
        self.ctx = pd.read_parquet(CONTEXT, columns=ctx_cols)
        fam_cols = [
            "cell_id",
            "road_access_context",
            "origin_semantics",
            *[f"drive_time_to_nearest_{c}_min" for c, *_ in EDU_HEALTH],
            *[f"{c}_unresolved_reason" for c, *_ in EDU_HEALTH],
        ]
        fam = pd.read_parquet(FAMILY, columns=fam_cols)
        assert (fam["origin_semantics"] == "CANONICAL_AOI_ANALYSIS_POINT").all(), (
            "family artifact must use corrected origins"
        )
        haz = pd.read_parquet(
            HAZARD,
            columns=[
                "cell_id",
                "clipped_area_km2",
                "flood_severity",
                "landslide_severity",
                "seismic_shaking_severity",
                "engineering_mitigation_action",
                "regional_search_action",
            ],
        )
        ter = pd.read_parquet(TERRAIN, columns=["cell_id", "elev_median_m"])
        df = self.ctx.merge(fam.drop(columns=["road_access_context"]), on="cell_id", validate="1:1")
        df = df.merge(haz, on="cell_id", validate="1:1").merge(ter, on="cell_id", validate="1:1")
        assert len(df) == len(self.ctx) == 162_073
        # both artifacts share the canonical origins, so their routable sets must agree (vocabularies differ)
        fam_routable = (
            fam.set_index("cell_id")
            .loc[df.cell_id, "road_access_context"]
            .str.startswith("CONNECTED_ROAD")
        )
        assert (
            fam_routable.to_numpy()
            == (df.road_access_context == "CONNECTED_ROAD_WITHIN_SNAP_DISTANCE").to_numpy()
        ).all()
        self.df = df
        self.gi = GridIndex(df["cell_id"].tolist())
        g = self.gi
        self.extent = (g.e0 * 500, (g.e0 + g.w) * 500, g.n0 * 500, (g.n0 + g.h) * 500)
        self.routable = (
            df["road_access_context"] == "CONNECTED_ROAD_WITHIN_SNAP_DISTANCE"
        ).to_numpy()

        self.prov = gpd.read_file(BOUNDARIES, layer="province_boundaries").to_crs(CRS)
        self.dist = gpd.read_file(BOUNDARIES, layer="district_boundaries").to_crs(CRS)
        self.aoi = shapely.union_all(self.prov.geometry.values)
        roads = gpd.read_file(ROADS, layer="major_roads").to_crs(CRS).clip(self.aoi)
        self.trunk = roads[roads["highway"] == "trunk"]
        self.primary = roads[roads["highway"] == "primary"]
        self.secondary = roads[roads["highway"] == "secondary"]
        self.hill = self._hillshade()
        self.labels = self._labels()

    # -- rasters
    def raster(self, values) -> np.ndarray:
        a = np.full((self.gi.h, self.gi.w), np.nan)
        a[self.gi.row, self.gi.col] = np.asarray(values, dtype=float)
        return a

    def rgba(self, codes: np.ndarray, colors: dict[int, str], alpha: float = 1.0) -> np.ndarray:
        img = np.zeros((self.gi.h, self.gi.w, 4))
        r = self.raster(codes)
        for k, c in colors.items():
            img[r == k] = to_rgba(c, alpha)
        return img

    def _hillshade(self) -> np.ndarray:
        z = self.raster(self.df["elev_median_m"].to_numpy())
        inside = np.isfinite(z)
        filled = np.where(inside, z, np.nanmedian(z))
        # LightSource expects row 0 = north; the grid has row 0 = south, so shade the flipped array and flip back
        hs = LightSource(azdeg=315, altdeg=40).hillshade(
            np.flipud(filled), vert_exag=2.0, dx=500, dy=500
        )
        hs = np.flipud(hs)
        hs[~inside] = np.nan
        return hs

    def _labels(self) -> pd.DataFrame:
        rows = []
        for f in sorted(DOPA.glob("*/dopa_gis02_*.json")):
            rows += json.loads(f.read_text("utf-8"))
        office = {}
        for r in rows:
            name = (r.get("oct_side01_name") or "").replace(" ", "").replace("​", "")
            if not name.startswith("ที่ว่าการอำเภอ") or "สาขา" in name:
                continue
            try:
                lon, lat = float(r["oct_side01_lon"]), float(r["oct_side01_lat"])
            except (TypeError, ValueError):
                continue
            office.setdefault(r["aname"], (lon, lat))
        to_utm = Transformer.from_crs(4326, CRS, always_xy=True)
        out = []
        for tier, table in (("primary", PRIMARY_LABELS), ("secondary", SECONDARY_LABELS)):
            for pcode, (th, en) in table.items():
                d = self.dist[self.dist["adm2_pcode"] == pcode].iloc[0]
                src, ll = "DOPA_GIS02_DISTRICT_OFFICE", office.get(d["adm2_name_th"])
                if ll is not None:
                    x, y = to_utm.transform(*ll)
                    if not d.geometry.contains(shapely.Point(x, y)):
                        ll = None  # e.g. a mis-geocoded office point; never trust a point outside its own district
                if ll is None:
                    src, ll = "M2D_REFERENCE_TOWN", FALLBACK_LONLAT[pcode]
                x, y = to_utm.transform(*ll)
                out.append(
                    {
                        "pcode": pcode,
                        "th": th,
                        "en": en,
                        "tier": tier,
                        "x": x,
                        "y": y,
                        "source": src,
                        "lon": ll[0],
                        "lat": ll[1],
                    }
                )
        return pd.DataFrame(out)


SERVICE_COMPONENTS = [
    "grocery_or_supermarket",
    "market",
    "pharmacy",
    "bank_or_financial",
    "fuel",
    "public_administration",
    "general_retail_or_service",
    "convenience_store",
]
SERVICE_TH = {
    "grocery_or_supermarket": "ร้านของชำ / ซูเปอร์มาร์เก็ต",
    "market": "ตลาด",
    "pharmacy": "ร้านขายยา",
    "bank_or_financial": "ธนาคาร / ATM",
    "fuel": "สถานีน้ำมัน",
    "public_administration": "หน่วยงานราชการ",
    "general_retail_or_service": "ร้านค้า / บริการทั่วไป",
    "convenience_store": "ร้านสะดวกซื้อ",
}
# (column stem, Thai title, English title)
EDU_HEALTH = [
    ("primary_school", "โรงเรียนประถม", "Primary school"),
    ("secondary_school", "โรงเรียนมัธยม (รวมต้น+ปลาย)", "Secondary school (pooled)"),
    ("hospital", "โรงพยาบาล", "Hospital"),
    ("higher_level_hospital", "โรงพยาบาลระดับสูง / ศูนย์ส่งต่อ", "Higher-level / referral hospital"),
]
TIME_BANDS = [
    (0, 15, "≤ 15"),
    (15, 30, "15–30"),
    (30, 45, "30–45"),
    (45, 60, "45–60"),
    (60, 90, "60–90"),
    (90, 1e9, "> 90"),
]
TIME_COLORS = [
    "#1D3F56",
    "#2F6585",
    "#5B90AE",
    "#8FB8CC",
    "#BFD9E3",
    "#E2EFF2",
]  # cool blues; unresolved stays warm grey


# ---------------------------------------------------------------- drawing helpers
def quad_axes(fig, i: int):
    """2 x 2 panel layout below a three-line header."""
    return fig.add_axes([0.02 + (i % 2) * 0.49, 0.475 - (i // 2) * 0.435, 0.47, 0.385])


def new_fig(w: float, h: float):
    return plt.figure(figsize=(w, h))


def frame(ax, c: Ctx, *, districts=True, pad=4000):
    ax.set_xlim(c.extent[0] - pad, c.extent[1] + pad)
    ax.set_ylim(c.extent[2] - pad, c.extent[3] + pad)
    ax.set_aspect("equal")
    ax.set_axis_off()
    if districts:
        c.dist.boundary.plot(ax=ax, color=DIST_EDGE, linewidth=0.3, zorder=5)
    c.prov.boundary.plot(ax=ax, color=PROV_EDGE, linewidth=0.9, zorder=6)


def relief(ax, c: Ctx, alpha=0.32, zorder=1):
    ax.imshow(
        c.hill,
        origin="lower",
        extent=c.extent,
        cmap="Greys_r",
        vmin=0,
        vmax=1,
        alpha=alpha,
        interpolation="bilinear",
        zorder=zorder,
    )


def show_rgba(ax, c: Ctx, img, zorder=2):
    ax.imshow(img, origin="lower", extent=c.extent, interpolation="nearest", zorder=zorder)


def put_labels(ax, c: Ctx, *, tiers=("primary",), size=7.5, english=False, color=INK):
    halo = [pe.withStroke(linewidth=2.4, foreground=PAPER)]
    for r in c.labels.itertuples():
        if r.tier not in tiers:
            continue
        big = r.tier == "primary"
        ax.plot(
            r.x,
            r.y,
            "o",
            ms=2.6 if big else 2.0,
            mfc=color if big else MUTED,
            mec=PAPER,
            mew=0.6,
            zorder=20,
        )
        txt = f"{r.th}\n{r.en}" if english else r.th
        dx, dy, ha = LABEL_OFFSET.get(r.pcode, (2500, 1200, "left"))
        ax.text(
            r.x + dx,
            r.y + dy,
            txt,
            ha=ha,
            fontsize=size if big else size - 1.2,
            color=color if big else MUTED,
            fontweight="bold" if big else "normal",
            path_effects=halo,
            zorder=21,
            linespacing=0.95,
        )


def scale_bar(ax, c: Ctx, km=50, loc=(0.05, 0.04)):
    x0 = c.extent[0] + (c.extent[1] - c.extent[0]) * loc[0]
    y0 = c.extent[2] + (c.extent[3] - c.extent[2]) * loc[1]
    seg = km * 1000 / 2
    for i in range(2):
        ax.add_patch(
            Rectangle(
                (x0 + i * seg, y0),
                seg,
                1800,
                facecolor=INK if i == 0 else PAPER,
                edgecolor=INK,
                linewidth=0.6,
                zorder=30,
            )
        )
    for i, t in enumerate(["0", f"{km // 2}", f"{km} km"]):
        ax.text(x0 + i * seg, y0 + 4200, t, ha="center", fontsize=6.5, color=INK, zorder=30)


def north_arrow(ax, c: Ctx, loc=(0.93, 0.90)):
    x = c.extent[0] + (c.extent[1] - c.extent[0]) * loc[0]
    y = c.extent[2] + (c.extent[3] - c.extent[2]) * loc[1]
    ax.annotate(
        "",
        xy=(x, y + 14000),
        xytext=(x, y),
        arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 1.1},
        zorder=30,
    )
    ax.text(x, y + 16500, "N", ha="center", fontsize=9, fontweight="bold", zorder=30)


def legend(ax, items, *, title=None, loc="lower left", ncol=1, fontsize=7, anchor=None):
    handles = [
        Patch(facecolor=col, edgecolor="#8A857B", linewidth=0.4, label=lab) for lab, col in items
    ]
    kw = {"bbox_to_anchor": anchor} if anchor else {}
    lg = ax.legend(
        handles=handles,
        title=title,
        loc=loc,
        ncol=ncol,
        fontsize=fontsize,
        title_fontsize=fontsize + 0.5,
        frameon=True,
        framealpha=0.92,
        edgecolor="#CFCBC2",
        **kw,
    )
    lg.get_frame().set_facecolor(PAPER)
    lg._legend_box.align = "left"
    lg.set_zorder(50)
    return lg


def header(fig, title_th: str, title_en: str, sub: str | None = None):
    h = fig.get_figheight()  # spacing in inches so short and tall plates look the same
    y = 1 - 0.22 / h
    fig.text(0.03, y, title_th, fontsize=17, fontweight="bold", va="top")
    fig.text(0.03, y - 0.42 / h, title_en, fontsize=10.5, color=MUTED, va="top")
    if sub:
        fig.text(0.03, y - 0.72 / h, sub, fontsize=8.5, color=INK, va="top", wrap=True)


def footer(fig, sources: str, y=0.012):
    fig.text(0.03, y + 0.016, NOT_A_SCORE, fontsize=7, color=MUTED)
    fig.text(
        0.03,
        y,
        f"ที่มา / Sources: {sources} · snapshot {SNAPSHOT} · HearthMap Briefing v0.1 (review PENDING)",
        fontsize=6.6,
        color=MUTED,
    )


def save(fig, name: str):
    MAPS.mkdir(parents=True, exist_ok=True)
    fig.savefig(MAPS / f"{name}.png", dpi=150)
    plt.close(fig)
    print("wrote", MAPS / f"{name}.png")


def banded(values: np.ndarray, no_road: np.ndarray) -> np.ndarray:
    """Codes 1..6 = time bands, 8 = no connected road within 1 km, 9 = unresolved for another recorded reason."""
    v = np.asarray(values, dtype=float)
    code = np.full(len(v), 9, dtype=int)
    for i, (lo, hi, _) in enumerate(TIME_BANDS, start=1):
        code[(v > lo if lo > 0 else v >= lo) & (v <= hi)] = i
    code[no_road] = 8
    return code


def band_colors() -> dict[int, str]:
    return {**{i + 1: col for i, col in enumerate(TIME_COLORS)}, 8: NO_DATA, 9: NO_ROUTE}


def band_legend_items(other_reason: str) -> list[tuple[str, str]]:
    items = [(f"{lab} นาที", col) for (_, _, lab), col in zip(TIME_BANDS, TIME_COLORS, strict=True)]
    items.append(("ยังไม่ทราบ: ไม่มีถนนเชื่อมใน 1 กม. (UNRESOLVED)", NO_DATA))
    items.append((other_reason, NO_ROUTE))
    return items


# ---------------------------------------------------------------- plates
def plate_overview(c: Ctx) -> None:
    fig = new_fig(11, 12.4)
    ax = fig.add_axes([0.02, 0.06, 0.96, 0.82])
    relief(ax, c, alpha=0.55)
    built = c.raster(c.df["built_ghsl2020_intensity_fraction_of_nominal_grid_cell"].to_numpy())
    img = np.zeros((*built.shape, 4))
    img[..., :3] = to_rgba("#5B3A29")[:3]
    img[..., 3] = np.clip(np.nan_to_num(built) / 0.35, 0, 1) * 0.85
    show_rgba(ax, c, img, zorder=3)
    c.secondary.plot(ax=ax, color="#C9B48A", linewidth=0.35, zorder=7)
    c.primary.plot(ax=ax, color="#B07A3B", linewidth=0.7, zorder=8)
    c.trunk.plot(ax=ax, color="#8C3B2E", linewidth=1.1, zorder=9)
    frame(ax, c)
    put_labels(ax, c, tiers=("primary", "secondary"), size=8.5, english=True)
    halo = [pe.withStroke(linewidth=3, foreground=PAPER)]
    W, H = c.extent[1] - c.extent[0], c.extent[3] - c.extent[2]
    for th, en, fx, fy in (
        ("จังหวัดเชียงใหม่", "Chiang Mai", 0.04, 0.42),
        ("จังหวัดเชียงราย", "Chiang Rai", 0.80, 0.955),
        ("จังหวัดพะเยา", "Phayao", 0.76, 0.40),
    ):
        name = f"{th}\n{en}"
        ax.text(
            c.extent[0] + W * fx,
            c.extent[2] + H * fy,
            name,
            fontsize=13,
            color="#5A554C",
            fontweight="bold",
            ha="left",
            path_effects=halo,
            zorder=15,
            linespacing=1.0,
        )
    scale_bar(ax, c)
    north_arrow(ax, c, loc=(0.10, 0.86))
    legend(
        ax,
        [
            ("ทางหลวงสายหลัก (OSM trunk)", "#8C3B2E"),
            ("ทางหลวงสายรอง (OSM primary)", "#B07A3B"),
            ("ถนนสาย secondary", "#C9B48A"),
            ("พื้นที่สิ่งปลูกสร้าง (GHSL built-up, เข้ม = หนาแน่นกว่า)", "#5B3A29"),
            ("ภูมิประเทศ (เงาความสูง DEM)", "#B8B3A8"),
        ],
        title="สัญลักษณ์",
        loc="lower right",
    )
    header(
        fig,
        "ภาพรวมพื้นที่ศึกษา HearthMap",
        "HearthMap overview: Chiang Mai · Chiang Rai · Phayao (AOI ≈ 39,930 km², 162,073 nominal 500 m cells)",
        "ชื่อสถานที่เป็นจุดอ้างอิงเพื่อการวางทิศทางเท่านั้น (REFERENCE LOCATIONS) ไม่ใช่พื้นที่ที่แนะนำ และไม่ใช่ Candidate Zone · ตำแหน่งจุด = ที่ว่าการอำเภอ (DOPA GIS02) หรือจุดอ้างอิงเมืองของ M2D",
    )
    footer(
        fig,
        "OCHA COD-AB boundaries, OSM roads (M1A), GHS-BUILT-S 2020, Copernicus GLO-30 DEM, DOPA GIS02",
    )
    save(fig, "00-hearthmap-overview")


def plate_hazard(c: Ctx) -> dict:
    d = c.df
    SEV = {"NONE": 1, "VERIFY": 2, "STRONG": 3, "NOT_ASSESSED": 4, "UNRESOLVED": 5}
    panels = [
        (
            "น้ำท่วม (Flood evidence)",
            d["flood_severity"].map(SEV).to_numpy(),
            {1: "#F1EEE6", 2: "#9FC2D6", 3: "#2F6690", 4: "#D9D9D9", 5: "#8E8E8E"},
            [
                ("ไม่พบหลักฐานที่ trigger", "#F1EEE6"),
                ("ควรตรวจสอบ (VERIFY)", "#9FC2D6"),
                ("หลักฐานแรง (STRONG)", "#2F6690"),
            ],
        ),
        (
            "ดินถล่ม / ความลาดชัน (Landslide / terrain)",
            d["landslide_severity"].map(SEV).to_numpy(),
            {1: "#F1EEE6", 2: "#E3BE7E", 3: "#9C5A2E", 4: "#D9D9D9", 5: "#8E8E8E"},
            [
                ("ไม่พบหลักฐานที่ trigger", "#F1EEE6"),
                ("ควรตรวจสอบ (VERIFY)", "#E3BE7E"),
                ("หลักฐานแรง (STRONG)", "#9C5A2E"),
                ("ไม่ได้ประเมิน (NOT_ASSESSED)", "#D9D9D9"),
            ],
        ),
        (
            "แผ่นดินไหว → การออกแบบโครงสร้าง (Seismic → engineering)",
            np.where(
                d["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED",
                3,
                d["seismic_shaking_severity"].map(SEV).to_numpy(),
            ),
            {1: "#F1EEE6", 2: "#C9C3DD", 3: "#6C67A3", 5: "#8E8E8E"},
            [
                ("ไม่ trigger การออกแบบพิเศษ", "#F1EEE6"),
                ("ควรตรวจสอบ (VERIFY)", "#C9C3DD"),
                (
                    "ต้องออกแบบรับแรงแผ่นดินไหว\n(SEISMIC_DESIGN_REQUIRED — ไม่ใช่การหลีกเลี่ยงพื้นที่)",
                    "#6C67A3",
                ),
                ("ยังไม่ทราบ (UNRESOLVED)", "#8E8E8E"),
            ],
        ),
        (
            "การกระทำเชิงภูมิภาคที่ได้ (Integrated regional search action)",
            d["regional_search_action"]
            .map(
                {
                    "CONTINUE_SEARCH": 1,
                    "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION": 2,
                    "DEPRIORITIZE_REGION": 3,
                    "UNRESOLVED": 5,
                }
            )
            .to_numpy(),
            {1: "#F1EEE6", 2: "#E3BE7E", 3: "#8E4A3A", 5: "#8E8E8E"},
            [
                ("ค้นหาต่อได้ (CONTINUE_SEARCH) — ไม่ได้แปลว่า 'ดี'", "#F1EEE6"),
                ("ค้นหาต่อ แต่ระวังหลีกเลี่ยง (WITH_AVOIDANCE_CAUTION)", "#E3BE7E"),
                ("ลดลำดับความสำคัญ (DEPRIORITIZE_REGION)", "#8E4A3A"),
                ("ยังไม่ทราบ (UNRESOLVED)", "#8E8E8E"),
            ],
        ),
    ]
    fig = new_fig(14, 15.2)
    for i, (ttl, codes, cols, items) in enumerate(panels):
        ax = quad_axes(fig, i)
        show_rgba(ax, c, c.rgba(codes, cols))
        relief(ax, c, alpha=0.18, zorder=3)
        frame(ax, c)
        put_labels(ax, c, size=6.8)
        ax.set_title(ttl, fontsize=11, fontweight="bold", loc="left")
        legend(ax, items, loc="lower right", fontsize=6.6)
    header(
        fig,
        "ฐานข้อมูลภัยธรรมชาติ: มีหลักฐานอะไรอยู่แล้วบ้าง",
        "Hazard foundation (M1E provisional integration) — four separate evidence families, no scalar hazard score",
        "ความรุนแรงของภัย ≠ ผลต่อการเลือกที่ดิน · การออกแบบรับแรงแผ่นดินไหว ≠ การหลีกเลี่ยงพื้นที่ · สีอ่อนแปลว่า 'ไม่มีหลักฐานที่ trigger' ไม่ได้แปลว่าปลอดภัย",
    )
    footer(
        fig,
        "M1E natural-hazard-actions (GISTDA flood, DMR landslide, DMR/TMD/USGS seismic; BALANCED + FLOOD_ANY_SOURCE; M1E human review PENDING)",
    )
    save(fig, "01-hazard-foundation")
    a = d["clipped_area_km2"]
    return {
        "regional_search_action_area_share": {
            k: round(float(a[d.regional_search_action == k].sum() / a.sum()), 4)
            for k in d.regional_search_action.unique()
        },
        "seismic_design_required_area_share": round(
            float(a[d.engineering_mitigation_action == "SEISMIC_DESIGN_REQUIRED"].sum() / a.sum()),
            4,
        ),
        "flood_strong_area_share": round(float(a[d.flood_severity == "STRONG"].sum() / a.sum()), 4),
        "landslide_strong_area_share": round(
            float(a[d.landslide_severity == "STRONG"].sum() / a.sum()), 4
        ),
        "landslide_not_assessed_area_share": round(
            float(a[d.landslide_severity == "NOT_ASSESSED"].sum() / a.sum()), 4
        ),
    }


def plate_routing(c: Ctx) -> dict:
    d = c.df
    pop = d["population_worldpop2025_mass_aoi_clipped"].fillna(0).to_numpy()
    built = d["built_ghsl2020_m2_aoi_clipped"].fillna(0).to_numpy()
    area = d["clipped_area_km2"].to_numpy()
    routable = c.routable
    ref_pop = float(
        np.median(pop[routable & (pop > 0)])
    )  # display reference only (same rule as M2D.1a)
    ref_built = float(np.median(built[routable & (built > 0)]))
    settle_like = ~routable & ((pop >= ref_pop) | (built >= ref_built))
    code = np.select([routable, settle_like], [1, 3], 2)
    fig = new_fig(14, 10.2)
    ax = fig.add_axes([0.01, 0.06, 0.56, 0.80])
    show_rgba(ax, c, c.rgba(code, {1: "#E4DCCB", 2: "#B9C3CC", 3: "#7A3F6E"}))
    relief(ax, c, alpha=0.22, zorder=3)
    c.trunk.plot(ax=ax, color="#6B5A45", linewidth=0.6, zorder=7)
    c.primary.plot(ax=ax, color="#6B5A45", linewidth=0.35, zorder=7)
    frame(ax, c)
    put_labels(ax, c, size=6.8)
    scale_bar(ax, c)
    legend(
        ax,
        [
            ("มีถนนเชื่อมโครงข่ายใน 1 กม. — คำนวณเวลาเดินทางได้", "#E4DCCB"),
            ("ยังไม่ทราบ (UNRESOLVED): ภูมิประเทศที่มีสัญญาณการตั้งถิ่นฐานต่ำ", "#B9C3CC"),
            ("ยังไม่ทราบ แต่มีสัญญาณการตั้งถิ่นฐาน — ควรทบทวน (display class)", "#7A3F6E"),
            ("ทางหลวงสายหลัก (OSM trunk / primary)", "#6B5A45"),
        ],
        loc="lower right",
        fontsize=6.8,
    )
    # bars: different weightings of the same unresolved set
    shares = [
        ("จำนวนเซลล์\ncells", float((~routable).mean())),
        ("พื้นที่\narea", float(area[~routable].sum() / area.sum())),
        (
            "ประชากรแบบจำลอง\nMODELLED population\n(WorldPop 2025)",
            float(pop[~routable].sum() / pop.sum()),
        ),
        ("สิ่งปลูกสร้าง\nbuilt-up m² (GHSL)", float(built[~routable].sum() / built.sum())),
    ]
    bx = fig.add_axes([0.63, 0.40, 0.33, 0.40])
    ys = np.arange(len(shares))[::-1]
    bx.barh(
        ys,
        [s * 100 for _, s in shares],
        color=["#9AA6B2", "#9AA6B2", "#7A3F6E", "#7A3F6E"],
        height=0.58,
    )
    for y_, (_, s) in zip(ys, shares, strict=True):
        bx.text(
            s * 100 + 1.2,
            y_,
            f"{round(s * 100 + 1e-9, 1):.1f}%" if s >= 0.1 else f"{s * 100:.2f}%",
            va="center",
            fontsize=12,
            fontweight="bold",
        )
    bx.set_yticks(ys, [lab for lab, _ in shares], fontsize=8.5)
    bx.set_xlim(0, 55)
    bx.set_xlabel("สัดส่วนที่อยู่ในเซลล์ UNRESOLVED (% ของ AOI)", fontsize=8.5)
    for s in ("top", "right"):
        bx.spines[s].set_visible(False)
    bx.set_facecolor(PAPER)
    fig.text(
        0.63,
        0.33,
        "ช่องว่างเชิงภูมิศาสตร์ขนาดใหญ่ ≠ ช่องว่างของการตั้งถิ่นฐานขนาดใหญ่\n"
        "Large geographic coverage gaps do not mean large settlement gaps.\n\n"
        "• UNRESOLVED = ไม่มีถนนที่เชื่อมกับโครงข่าย (OSM primary → unclassified)\n   ภายใน 1 กม. จากจุดวิเคราะห์ของเซลล์ — ไม่ใช่ 0 นาที และไม่เดาแทน\n"
        "• ส่วนใหญ่อยู่ในพื้นที่ภูเขา/ป่าที่มีการตั้งถิ่นฐานเบาบาง\n"
        "• ประชากรเป็น MODELLED estimate (WorldPop R2025A alpha) ไม่ใช่สำมะโน\n"
        f"• สีม่วง = เซลล์ unresolved ที่มีค่า ≥ มัธยฐานของเซลล์ที่ routable\n   (ประชากร {ref_pop:.1f} คน หรือ built-up {ref_built:,.0f} m²) — เกณฑ์เพื่อการแสดงผลเท่านั้น",
        fontsize=8.3,
        va="top",
        linespacing=1.35,
    )
    header(
        fig,
        "ถนนและการเข้าถึง: ส่วนไหนคำนวณได้ ส่วนไหนยังไม่ทราบ",
        "Road routing coverage (frozen BASELINE_DRIVE_TIME network, 1 km snap, canonical AOI analysis points)",
    )
    footer(
        fig,
        "M2D regional-context evidence (OSM road graph fingerprint 5c35e98882c3ac62), WorldPop R2025A, GHS-BUILT-S 2020, M2D.1a routing coverage QA",
    )
    save(fig, "02-routing-accessibility")
    return {
        "unresolved_cell_share": round(shares[0][1], 4),
        "unresolved_area_share": round(shares[1][1], 4),
        "unresolved_modelled_population_share": round(shares[2][1], 4),
        "unresolved_built_up_share": round(shares[3][1], 4),
        "settlement_like_unresolved_cells": int(settle_like.sum()),
        "cells_unresolved": int((~routable).sum()),
        "modelled_population_total": round(float(pop.sum())),
    }


def plate_edu_health(c: Ctx) -> dict:
    d = c.df
    no_road = ~c.routable
    fig = new_fig(14, 15.2)
    facts = {}
    for i, (stem, th, en) in enumerate(EDU_HEALTH):
        v = d[f"drive_time_to_nearest_{stem}_min"].to_numpy()
        ax = quad_axes(fig, i)
        show_rgba(ax, c, c.rgba(banded(v, no_road), band_colors()))
        relief(ax, c, alpha=0.15, zorder=3)
        frame(ax, c)
        put_labels(ax, c, size=6.6)
        ax.set_title(f"{th}  ·  {en}", fontsize=11, fontweight="bold", loc="left")
        other = "มีถนน แต่ไม่พบเส้นทางภายใน 120 นาที / ไม่ถึง" if np.isnan(v[~no_road]).any() else "—"
        legend(
            ax,
            band_legend_items(other),
            title="Baseline Drive Time (นาที)",
            loc="lower right",
            fontsize=6.4,
        )
        ok = np.isfinite(v)
        facts[stem] = {
            "routable_cells_with_route_share": round(float(ok.mean()), 4),
            "median_min_among_cells_with_route": round(float(np.nanmedian(v)), 1),
            "cells_routable_but_no_route": int((~ok & ~no_road).sum()),
        }
    header(
        fig,
        "การศึกษาและสาธารณสุข: เวลาขับรถโดยประมาณ (ไม่ใช่คุณภาพ)",
        "Education & healthcare Baseline Drive Time — corrected M2A.2 origin artifact (canonical AOI analysis points)",
        "เวลาที่สั้นกว่า ≠ ดีกว่าโดยอัตโนมัติ · ข้อมูลโรงเรียน STALE/PARTIAL (DOPA 2021 + OBEC 2020) · โรงพยาบาลจาก MoPH (เน้นของรัฐ) · ระดับโรงพยาบาล ≠ ขีดความสามารถ (ไม่มีข้อมูล ER/ICU/trauma) · ปลายทางจำกัดใน 3 จังหวัด (BOUNDARY_LIMITED)",
    )
    footer(
        fig,
        "outputs/m2a2-origin family-infrastructure-evidence (MoPH public hospital layer, DOPA/OBEC school registers), OSM road graph; M2A human review PENDING",
    )
    save(fig, "03-education-healthcare")
    return facts


def plate_settlement(c: Ctx) -> dict:
    d = c.df
    fig = new_fig(14, 8.6)
    pop = d["population_worldpop2025_intensity_per_nominal_grid_cell_km2"].to_numpy(dtype=float)
    built = d["built_ghsl2020_intensity_fraction_of_nominal_grid_cell"].to_numpy(dtype=float)
    specs = [
        (
            "ความหนาแน่นประชากร (แบบจำลอง)",
            "WorldPop R2025A — MODELLED people / km² (log)",
            pop,
            "YlOrBr",
            LogNorm(vmin=1, vmax=10_000),
            "คน / ตร.กม. (แบบจำลอง)",
        ),
        (
            "ความหนาแน่นสิ่งปลูกสร้าง",
            "GHS-BUILT-S 2020 — built-up fraction of 500 m cell",
            built,
            "BuPu",
            PowerNorm(0.5, vmin=0, vmax=0.5),
            "สัดส่วนพื้นที่สิ่งปลูกสร้าง (สเกลรากที่สอง, ≥ 0.5 = สีเข้มสุด)",
        ),
    ]
    for i, (th, en, v, cmap, norm, lab) in enumerate(specs):
        ax = fig.add_axes([0.02 + i * 0.49, 0.08, 0.47, 0.70])
        zero = c.raster(np.where(v > 0, np.nan, 1.0))
        ax.imshow(
            np.where(np.isfinite(zero), 1, np.nan),
            origin="lower",
            extent=c.extent,
            cmap="Greys",
            vmin=0,
            vmax=8,
            interpolation="nearest",
            zorder=1,
        )
        vv = c.raster(np.where(v > 0, v, np.nan))
        im = ax.imshow(
            vv,
            origin="lower",
            extent=c.extent,
            cmap=cmap,
            norm=norm,
            interpolation="nearest",
            zorder=2,
        )
        relief(ax, c, alpha=0.14, zorder=3)
        frame(ax, c)
        put_labels(ax, c, size=6.8)
        ax.set_title(f"{th}\n{en}", fontsize=10.5, fontweight="bold", loc="left")
        cax = fig.add_axes([0.06 + i * 0.49, 0.105, 0.16, 0.012])
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.set_label(lab, fontsize=7)
        cb.ax.tick_params(labelsize=6.5)
        fig.text(0.24 + i * 0.49, 0.105, "สีเทาอ่อน = 0 / ไม่มีสัญญาณ", fontsize=7, color=MUTED)
    header(
        fig,
        "การตั้งถิ่นฐานและรูปแบบสิ่งปลูกสร้าง",
        "Settlement & built form — two different variables, side by side",
        "ความหนาแน่นประชากร ≠ สิ่งปลูกสร้าง ≠ ความสงบ (peacefulness) · WorldPop ใช้ GHSL เป็นตัวแปรร่วม จึงไม่ใช่หลักฐานยืนยันที่เป็นอิสระต่อกัน (PARTLY DEPENDENT)",
    )
    footer(
        fig,
        "WorldPop R2025A v1 (alpha, CC BY 4.0, AOI-clipped), JRC GHS-BUILT-S R2023A epoch 2020; M2D human review PASSED 2026-10-16",
    )
    save(fig, "04-settlement-built-form")
    return {
        "population_built_rank_correlation_note": "0.87 descriptive, PARTLY_DEPENDENT, not validation (M2D.1)"
    }


def plate_town_services(c: Ctx) -> dict:
    d = c.df
    no_road = ~c.routable
    fig = new_fig(14, 9.6)
    facts = {}
    for i, comp in enumerate(SERVICE_COMPONENTS):
        v = d[f"drive_time_to_nearest_service_{comp}_min"].to_numpy()
        ax = fig.add_axes([0.01 + (i % 4) * 0.245, 0.47 - (i // 4) * 0.40, 0.235, 0.36])
        show_rgba(ax, c, c.rgba(banded(v, no_road), band_colors()))
        frame(ax, c, districts=False)
        facts[comp] = round(float(np.nanmedian(v)), 1)
        ax.set_title(
            f"{SERVICE_TH[comp]}  ·  มัธยฐาน* {facts[comp]:.1f} นาที",
            fontsize=9.5,
            fontweight="bold",
            loc="left",
        )
    lg_ax = fig.add_axes([0.0, 0.0, 1, 0.06])
    lg_ax.set_axis_off()
    legend(lg_ax, band_legend_items("มีถนน แต่ไม่พบปลายทางประเภทนี้"), loc="center", ncol=4, fontsize=7)
    header(
        fig,
        "บริการในเมือง: หลักฐานรายองค์ประกอบ (component-level)",
        "Town services — Baseline Drive Time to the nearest OSM POI of each component (5,019 POIs after de-duplication)",
        "*มัธยฐานเฉพาะเซลล์ที่มีเส้นทาง (MEDIAN_AMONG_ROUTABLE_CELLS_ONLY) · การไม่มี POI ใน OSM ≠ ไม่มีบริการจริง · ยังไม่มีนิยาม 'บริการในเมืองที่เพียงพอ' และความต้องการ 35 นาทียังไม่ถูกใช้เป็นกฎ",
    )
    fig.text(0.03, 0.065, NOT_A_SCORE, fontsize=7, color=MUTED)
    save(fig, "05-town-services")

    # definition sensitivity
    core = d["drive_time_to_nearest_service_cluster_core_min"].to_numpy()
    broad = d["drive_time_to_nearest_service_cluster_broader_min"].to_numpy()
    assert set(d["service_cluster_core_definition_status"]) == {"CANDIDATE_DEFINITION"}
    assert set(d["service_cluster_broader_definition_status"]) == {"CANDIDATE_DEFINITION"}
    diff = core - broad
    fig = new_fig(14, 7.6)
    for i, (ttl, v) in enumerate(
        [
            ("CORE (ผู้สมัคร): ≥ 4 องค์ประกอบ ในระยะเชื่อม 400 ม.", core),
            ("BROADER (ผู้สมัคร): ≥ 3 องค์ประกอบ ในระยะเชื่อม 800 ม.", broad),
        ]
    ):
        ax = fig.add_axes([0.01 + i * 0.33, 0.12, 0.31, 0.62])
        show_rgba(ax, c, c.rgba(banded(v, no_road), band_colors()))
        frame(ax, c, districts=False)
        put_labels(ax, c, size=6)
        ax.set_title(
            f"{ttl}\nมัธยฐาน* {np.nanmedian(v):.1f} นาที", fontsize=9.5, fontweight="bold", loc="left"
        )
    ax = fig.add_axes([0.67, 0.12, 0.31, 0.62])
    dcode = np.select(
        [np.isnan(diff), diff <= 2, diff <= 5, diff <= 10, diff <= 20], [9, 1, 2, 3, 4], 5
    )
    dcode[no_road] = 8
    dcol = {
        1: "#EFEBE0",
        2: "#D8C9A8",
        3: "#B9976A",
        4: "#8C6239",
        5: "#5A3A1E",
        8: NO_DATA,
        9: NO_ROUTE,
    }
    show_rgba(ax, c, c.rgba(dcode, dcol))
    frame(ax, c, districts=False)
    ax.set_title(
        "ความต่าง CORE − BROADER (นาที)\nต่อเซลล์ (CORE ไกลกว่าหรือเท่ากันเสมอ)",
        fontsize=9.5,
        fontweight="bold",
        loc="left",
    )
    legend(
        ax,
        [
            ("≤ 2", dcol[1]),
            ("2–5", dcol[2]),
            ("5–10", dcol[3]),
            ("10–20", dcol[4]),
            ("> 20", dcol[5]),
            ("UNRESOLVED", NO_DATA),
        ],
        loc="lower right",
        fontsize=6.6,
        title="นาที",
    )
    lg_ax = fig.add_axes([0.0, 0.0, 0.66, 0.08])
    lg_ax.set_axis_off()
    legend(lg_ax, band_legend_items("มีถนน แต่ไม่พบคลัสเตอร์"), loc="center", ncol=4, fontsize=6.6)
    header(
        fig,
        "นิยาม 'บริการในเมือง' ยังไม่ถูกเลือก — ทั้งสองนิยามเป็นเพียงผู้สมัคร",
        "Town-service cluster definition sensitivity: NEITHER DEFINITION HAS BEEN SELECTED",
        "คำตอบเปลี่ยนตามนิยาม: ความต่างมากที่สุดในพื้นที่ที่บริการเบาบาง · *มัธยฐานเฉพาะเซลล์ที่มีเส้นทาง",
    )
    fig.text(0.68, 0.035, NOT_A_SCORE, fontsize=6.4, color=MUTED, wrap=True)
    save(fig, "05b-town-services-sensitivity")
    both = np.isfinite(core) & np.isfinite(broad)
    facts["core_median"] = round(float(np.median(core[both])), 2)
    facts["broader_median"] = round(float(np.median(broad[both])), 2)
    facts["paired_diff_median"] = round(float(np.median(diff[both])), 2)
    facts["paired_diff_p90"] = round(float(np.percentile(diff[both], 90)), 2)
    return facts


def plate_industry(c: Ctx) -> dict:
    a3 = gpd.read_file(next(OCHA.glob("*/tha_admin_boundaries.gdb.zip")), layer="tha_admin3")
    a3 = a3[a3["adm1_pcode"].isin(["TH50", "TH56", "TH57"])].to_crs(CRS)
    tam = pd.read_csv(TAMBON_TABLE)
    a3 = a3[["adm3_pcode", "geometry"]].merge(tam, on="adm3_pcode", how="left")
    osm = pd.read_csv(OSM_GEOM)
    osm = gpd.GeoDataFrame(osm, geometry=shapely.from_wkt(osm["wkt"]), crs=CRS)

    fig = new_fig(15, 8.4)
    # (a) DIW tambon register context
    ax = fig.add_axes([0.005, 0.10, 0.325, 0.70])
    n = a3["diw_registered_factories"].fillna(0)
    bins = [
        (0, 0, "0"),
        (1, 2, "1–2"),
        (3, 5, "3–5"),
        (6, 10, "6–10"),
        (11, 25, "11–25"),
        (26, 1e9, "> 25"),
    ]
    cols = ["#F3F0E8", "#E6DCC8", "#D2BE9C", "#B48F63", "#8A6238", "#5C3D1E"]
    for (lo, hi, _), col in zip(bins, cols, strict=True):
        a3[(n >= lo) & (n <= hi)].plot(ax=ax, color=col, linewidth=0, zorder=2)
    a3.boundary.plot(ax=ax, color="#FFFFFF", linewidth=0.15, zorder=3)
    frame(ax, c, districts=False)
    put_labels(ax, c, size=6)
    ax.set_title(
        "ADMINISTRATIVE CONTEXT\nทะเบียนโรงงาน DIW รายตำบล (ไม่มีพิกัดโรงงาน)",
        fontsize=9.5,
        fontweight="bold",
        loc="left",
    )
    legend(
        ax,
        [(f"{lab} รายการ", col) for (_, _, lab), col in zip(bins, cols, strict=True)],
        loc="lower right",
        fontsize=6.4,
        title="ทั้งตำบลได้สีเดียวกัน",
    )

    # (b) DPIM register status, tambon level
    ax = fig.add_axes([0.335, 0.10, 0.325, 0.70])
    opened = a3["dpim_stone_crushing_opened_register_status"].fillna(0) > 0
    unexp = a3["dpim_concessions_unexpired_register_status"].fillna(0) > 0
    anyrec = (a3["dpim_stone_crushing_licences"].fillna(0) + a3["dpim_concessions"].fillna(0)) > 0
    legacy = a3["legacy_dpim_2016_concessions"].fillna(0) > 0
    cat = np.select([opened & unexp, opened, unexp, anyrec, legacy], [1, 2, 3, 4, 5], 0)
    ccol = {0: "#F3F0E8", 1: "#5A2E4F", 2: "#9B5A86", 3: "#5F7FA0", 4: "#CDC6D6", 5: "#E5DFD0"}
    for k, col in ccol.items():
        sub = a3[cat == k]
        if len(sub):
            sub.plot(
                ax=ax,
                color=col,
                linewidth=0,
                zorder=2,
                hatch="////" if k == 5 else None,
                edgecolor="#B9AE95" if k == 5 else None,
            )
    a3.boundary.plot(ax=ax, color="#FFFFFF", linewidth=0.15, zorder=3)
    frame(ax, c, districts=False)
    put_labels(ax, c, size=6)
    ax.set_title(
        "REGISTER STATUS (DPIM)\nใบอนุญาตโม่บดหิน / ประทานบัตร รายตำบล",
        fontsize=9.5,
        fontweight="bold",
        loc="left",
    )
    legend(
        ax,
        [
            ("โม่บดหินสถานะ 'เปิดการ' + ประทานบัตรยังไม่หมดอายุ", ccol[1]),
            ("โม่บดหิน สถานะทะเบียน 'เปิดการ'", ccol[2]),
            ("ประทานบัตร สถานะทะเบียนยังไม่หมดอายุ", ccol[3]),
            ("มีบันทึก แต่สถานะอื่น / หมดอายุ", ccol[4]),
            ("LEGACY CONTEXT: ประทานบัตรปี 2016 เท่านั้น", ccol[5]),
            ("ไม่มีบันทึกในแหล่งที่ได้มา", ccol[0]),
        ],
        loc="lower right",
        fontsize=6.2,
        title="สถานะทะเบียน ≠ การดำเนินงานจริง",
    )

    # (c) located OSM geometry
    ax = fig.add_axes([0.665, 0.10, 0.325, 0.70])
    relief(ax, c, alpha=0.30)
    frame(ax, c)
    kinds = [
        ("OSM_INDUSTRIAL_LANDUSE", "#8C3B2E", "o", "พื้นที่อุตสาหกรรม (landuse=industrial)"),
        ("OSM_WORKS", "#D08C34", "s", "โรงงาน / works (man_made=works)"),
        ("OSM_QUARRY", "#3F5E7A", "^", "เหมือง / บ่อหิน (landuse=quarry)"),
    ]
    present = set(osm["kind"])
    for kind, col, mk, lab in kinds:
        sub = osm[osm["kind"] == kind]
        if not len(sub):
            continue
        poly = sub[sub.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(poly):
            poly.plot(ax=ax, color=col, edgecolor=col, linewidth=0.6, zorder=8)
        pts = sub.geometry.representative_point()
        ax.scatter(
            pts.x,
            pts.y,
            s=11,
            marker=mk,
            color=col,
            edgecolors=PAPER,
            linewidths=0.35,
            zorder=9,
            label=lab,
        )
    put_labels(ax, c, size=6)
    ax.set_title(
        "LOCATED OSM CONTEXT\nวัตถุที่มีตำแหน่งจริงใน OpenStreetMap",
        fontsize=9.5,
        fontweight="bold",
        loc="left",
    )
    lg = ax.legend(
        loc="lower right",
        fontsize=6.4,
        frameon=True,
        framealpha=0.92,
        title="ความครบถ้วนของ OSM ไม่สม่ำเสมอ",
        title_fontsize=6.6,
    )
    lg.get_frame().set_facecolor(PAPER)
    lg.set_zorder(50)
    header(
        fig,
        "อุตสาหกรรม เหมือง และบริบทความรำคาญ",
        "Industry, mining & nuisance context — three evidence types at three different spatial resolutions",
        "มีโรงงาน ≠ ยืนยันว่ารบกวน · สถานะใบอนุญาต ≠ การดำเนินงานปัจจุบัน · ข้อมูลรายตำบล ≠ ตำแหน่งที่แน่นอน · ไม่มี buffer หรือการตัดพื้นที่ใด ๆ",
    )
    footer(
        fig,
        "DIW factory registers (2026-10-01, outside industrial estates), DPIM stone-crushing & concession exports, DPIM 2016 snapshot (legacy), OSM (M2D.1 geometry)",
    )
    save(fig, "06-industry-mining-context")
    return {
        "osm_kinds": {k: int((osm["kind"] == k).sum()) for k in sorted(present)},
        "tambons_opened_stone_crushing": int(opened.sum()),
        "tambons_unexpired_concession": int(unexp.sum()),
        "diw_factories_aoi": int(n.sum()),
    }


STATE_GROUP = {
    "READY": ("KNOWN", "#3E5C76"),
    "READY_WITH_LIMITATIONS": ("KNOWN WITH LIMITATIONS", "#7895AE"),
    "PARTIAL": ("PARTIAL", "#B7C6D2"),
    "PROXY_ONLY": ("PROXY ONLY", "#E2C48E"),
    "NOT_EVALUABLE": ("UNRESOLVED / NOT EVALUABLE", "#C9C5BD"),
    "BLOCKED_BY_SOURCE_GAP": ("BLOCKED BY SOURCE GAP", "#A39C90"),
    "PARCEL_VERIFICATION_ONLY": ("PARCEL VERIFICATION REQUIRED", "#9B6A5C"),
    "FIELD_VERIFICATION_ONLY": ("FIELD VERIFICATION REQUIRED", "#C79A8B"),
    "INTENTIONALLY_NOT_USED": ("NOT USED (by design)", "#F0EDE6"),
}
ENTRY_TH = {
    "EDU-KG": "อนุบาล",
    "EDU-PRIMARY": "ประถม",
    "EDU-LOWSEC": "มัธยมต้น",
    "EDU-UPSEC": "มัธยมปลาย",
    "ALT-CHOICES": "ทางเลือกโรงเรียนหลายแห่ง",
    "HC-PRIMARY": "หน่วยบริการปฐมภูมิ",
    "HC-HOSPITAL": "โรงพยาบาล",
    "HC-REGIONAL": "โรงพยาบาลศูนย์ / ส่งต่อ",
    "HC-CAPABILITY": "ขีดความสามารถ ER/ICU/trauma",
    "TOWN-SERVICES": "บริการในเมือง",
    "LAND-PRICE": "ราคาที่ดิน ≤ 500,000 บาท",
    "ELEC-GRID": "ไฟฟ้า (grid)",
    "WATER-PWA": "น้ำประปา กปภ.",
    "WATER-LOCAL": "ประปาท้องถิ่น",
    "WATER-VILLAGE": "ประปาหมู่บ้าน",
    "WATER-GROUND": "น้ำบาดาล / บ่อ",
    "FIBER": "อินเทอร์เน็ตไฟเบอร์",
    "ROAD-A-NETWORK": "การเชื่อมโครงข่ายถนน",
    "ROAD-B-LEGAL": "ทางเข้าออกตามกฎหมาย",
    "ROAD-C-ALLWEATHER": "ทางเข้าใช้ได้ทุกฤดู",
    "ROAD-D-SURFACE": "ผิวทาง",
    "ROAD-E-NOISE": "เสียงจากถนนสายหลัก",
    "NUIS-INDUSTRIAL": "ความรำคาญจากอุตสาหกรรม",
    "NUIS-MINING": "เหมือง / โม่หิน",
    "NUIS-NIGHTLIFE": "สถานบันเทิงกลางคืน",
    "SETTLE-PEACE": "ความสงบ / ความหนาแน่นต่ำ",
    "TERRAIN-PREF": "ภูมิประเทศลาดเอียงเล็กน้อย",
    "SITE-IMPROVE": "ความยินดีปรับปรุงพื้นที่",
    "PARCEL-AREA": "ขนาดแปลง",
}
STAGES = [
    ("REGIONAL_SCREENING", "Regional\nScreening"),
    ("CANDIDATE_ZONE_COMPARISON", "Candidate-zone\nComparison"),
    ("PARCEL_SHORTLIST", "Parcel\nShortlist"),
    ("PRE_PURCHASE_VERIFICATION", "Pre-purchase\nVerification"),
]


def plate_evidence_state() -> dict:
    plan = yaml.safe_load(EVALUABILITY.read_text("utf-8"))
    assert plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
    entries = [e for e in plan["entries"] if not e["id"].startswith("IRR-")]
    fig = new_fig(13, 14.5)
    ax = fig.add_axes([0.27, 0.10, 0.70, 0.78])
    nrow = len(entries)
    counts: dict[str, int] = {}
    for r, e in enumerate(entries):
        y = nrow - 1 - r
        for k, (stage, _) in enumerate(STAGES):
            state = e["stages"][stage][0]
            grp, col = STATE_GROUP[state]
            if stage == "REGIONAL_SCREENING":
                counts[grp] = counts.get(grp, 0) + 1
            ax.add_patch(
                Rectangle((k, y), 0.96, 0.9, facecolor=col, edgecolor=PAPER, linewidth=1.2)
            )
            dark = col in ("#3E5C76", "#7895AE", "#9B6A5C", "#A39C90")
            ax.text(
                k + 0.48,
                y + 0.45,
                grp.replace(" REQUIRED", "").replace(" / NOT EVALUABLE", ""),
                ha="center",
                va="center",
                fontsize=6.3,
                color=PAPER if dark else INK,
            )
        ax.text(
            -0.08,
            y + 0.45,
            f"{ENTRY_TH.get(e['id'], e['title'])}   ",
            ha="right",
            va="center",
            fontsize=8.6,
        )
        ax.text(
            -0.08, y + 0.08, f"{e['id']}   ", ha="right", va="center", fontsize=5.8, color=MUTED
        )
    for k, (_, lab) in enumerate(STAGES):
        ax.text(k + 0.48, nrow + 0.25, lab, ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xlim(-0.05, len(STAGES))
    ax.set_ylim(-0.2, nrow + 1.4)
    ax.set_axis_off()
    order = [
        "KNOWN",
        "KNOWN WITH LIMITATIONS",
        "PARTIAL",
        "PROXY ONLY",
        "UNRESOLVED / NOT EVALUABLE",
        "BLOCKED BY SOURCE GAP",
        "PARCEL VERIFICATION REQUIRED",
        "FIELD VERIFICATION REQUIRED",
        "NOT USED (by design)",
    ]
    cmap = {g: col for g, col in STATE_GROUP.values()}
    lg_ax = fig.add_axes([0.02, 0.01, 0.96, 0.07])
    lg_ax.set_axis_off()
    legend(
        lg_ax,
        [(g + ("  (ปัจจุบัน: 0 รายการ)" if g == "KNOWN" else ""), cmap[g]) for g in order],
        loc="center",
        ncol=3,
        fontsize=7.4,
    )
    header(
        fig,
        "สถานะของหลักฐาน: รู้อะไร รู้แค่ไหน และอะไรต้องรอตรวจที่แปลงจริง",
        "Evidence state per family requirement × decision stage (config/family-evaluability.yaml, M2C + M2D.1 + M2D.1e)",
        "สถานะเป็นหมวดหมู่ ไม่ใช่คะแนนความเชื่อมั่น และไม่ถูกรวมเป็นตัวเลขเดียว · ยังไม่มีรายการใดเป็น READY · FAMILY_SCORING_ALLOWED = false",
    )
    save(fig, "07-evidence-state")
    return {"regional_screening_state_counts": counts, "entries": nrow}


def plate_concept(c: Ctx) -> None:
    fig = new_fig(14, 8.6)
    W = fig.add_axes([0, 0, 1, 1])
    W.set_xlim(0, 100)
    W.set_ylim(0, 62)
    W.set_axis_off()

    def box(x, y, w, h, fc="#FFFFFF", ec="#CFCBC2", lw=0.8, r=0.6):
        W.add_patch(
            FancyBboxPatch(
                (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw
            )
        )

    W.text(
        2,
        59.5,
        "แนวคิดหน้าจอ HearthMap ในอนาคต (CONCEPT — NOT IMPLEMENTED)",
        fontsize=16,
        fontweight="bold",
        va="top",
    )
    W.text(
        2,
        56.6,
        "Future product concept: requirements · map · evidence explanation · candidate comparison. ไม่มีข้อมูลจริง ไม่มีฟังก์ชันที่ทำงานได้ ไม่มี Candidate Zone ที่ถูกสร้างขึ้น",
        fontsize=9,
        color=MUTED,
        va="top",
    )
    box(2, 4, 96, 50, fc="#F3F1EB")
    # left
    box(3, 18, 19, 35)
    W.text(4, 51.5, "ความต้องการของครอบครัว", fontsize=9.5, fontweight="bold", va="top")
    for i, t in enumerate(
        [
            "งบที่ดิน ≤ 500,000 บาท (MUST)",
            "ไฟเบอร์ก่อนซื้อ (MUST)",
            "ไฟฟ้า grid ก่อนซื้อ (MUST)",
            "รพ. ≤ 35 นาที (MUST)",
            "ประถม ≤ 25 นาที (MUST)",
            "ที่สงบ ความหนาแน่นต่ำ (STRONG)",
            "ภูมิประเทศลาดเล็กน้อย (PREF)",
        ]
    ):
        W.text(4.3, 48.6 - i * 2.2, "▢  " + t, fontsize=7.3, va="top")
    W.text(4, 32.5, "ชั้นข้อมูล (layers)", fontsize=9.5, fontweight="bold", va="top")
    for i, t in enumerate(
        ["ภัยธรรมชาติ (M1E)", "เวลาเดินทาง", "การตั้งถิ่นฐาน", "อุตสาหกรรม / เหมือง", "สถานะหลักฐาน"]
    ):
        W.text(4.3, 29.8 - i * 2.2, "◉  " + t if i == 0 else "○  " + t, fontsize=7.3, va="top")
    # center map: real relief thumbnail, no zones
    mx = fig.add_axes([0.235, 0.30, 0.39, 0.555])
    relief(mx, c, alpha=0.55)
    frame(mx, c)
    put_labels(mx, c, size=6)
    W.text(
        23.5,
        16.9,
        "แผนที่โต้ตอบ (interactive map) — ภาพนี้เป็นเพียงพื้นหลังภูมิประเทศ ไม่มีพื้นที่ใดถูกเลือก",
        fontsize=7,
        color=MUTED,
    )
    # right panel
    box(64, 18, 33, 35)
    W.text(65, 51.5, "คำอธิบายหลักฐาน (ตัวอย่างโครงร่าง)", fontsize=9.5, fontweight="bold", va="top")
    secs = [
        ("WHAT WE KNOW", "สิ่งที่รู้จากแหล่งข้อมูล (observed / source evidence)", "#3E5C76"),
        ("WHAT WE INFER", "สิ่งที่อนุมาน (derived evidence / proxy)", "#7895AE"),
        ("WHAT WE DON'T KNOW", "ช่องว่างหลักฐาน (unresolved / not assessed)", "#A39C90"),
        ("WHY THIS AREA IS STILL A CANDIDATE", "เหตุผลที่ยังอยู่ในการพิจารณา (อนาคต)", "#B7A88A"),
        ("WHAT TO VERIFY NEXT", "สิ่งที่ต้องตรวจที่แปลงจริง / ในพื้นที่", "#9B6A5C"),
    ]
    for i, (en, th, col) in enumerate(secs):
        y = 47.8 - i * 6.0
        W.add_patch(Rectangle((65, y - 4.4), 0.6, 4.4, color=col))
        W.text(66.3, y, en, fontsize=7.8, fontweight="bold", va="top")
        W.text(66.3, y - 1.7, th, fontsize=7, color=MUTED, va="top")
        W.add_patch(Rectangle((66.3, y - 3.9), 26, 0.55, color="#E6E2D9"))
    # bottom drawer
    box(3, 5, 94, 11.5)
    W.text(
        4,
        15.4,
        "เปรียบเทียบพื้นที่ผู้สมัคร (Candidate comparison drawer) — ยังไม่มีพื้นที่ผู้สมัคร: ตารางนี้ว่างโดยเจตนา",
        fontsize=9,
        fontweight="bold",
        va="top",
    )
    heads = [
        "พื้นที่",
        "ภัย (actions)",
        "เวลาเดินทาง",
        "การตั้งถิ่นฐาน",
        "บริบทความรำคาญ",
        "ราคาที่ดิน",
        "ต้องตรวจสอบ",
    ]
    for i, h in enumerate(heads):
        W.text(4.5 + i * 13.3, 12.2, h, fontsize=7.6, color=MUTED, va="top")
        for j in range(2):
            W.add_patch(Rectangle((4.5 + i * 13.3, 9.0 - j * 2.6), 11.5, 1.6, color="#EEEBE4"))
    W.text(
        50,
        2.0,
        "CONCEPT ONLY · ไม่มีคะแนน ไม่มีการจัดอันดับ ไม่มีคำแนะนำ · FAMILY_SCORING_ALLOWED = false",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    save(fig, "08-future-product-concept")


def main() -> int:
    c = Ctx()
    facts: dict = {
        "snapshot": SNAPSHOT,
        "cells": len(c.df),
        "aoi_area_km2": round(float(c.df["clipped_area_km2"].sum()), 1),
    }
    facts["labels"] = c.labels[["pcode", "th", "en", "tier", "source", "lon", "lat"]].to_dict(
        "records"
    )
    plate_overview(c)
    facts["hazard"] = plate_hazard(c)
    facts["routing"] = plate_routing(c)
    facts["education_healthcare"] = plate_edu_health(c)
    facts["settlement"] = plate_settlement(c)
    facts["town_services_median_min_among_routable"] = plate_town_services(c)
    facts["industry"] = plate_industry(c)
    facts["evidence_state"] = plate_evidence_state()
    plate_concept(c)
    (OUT / "briefing-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        json.dumps({k: v for k, v in facts.items() if k != "labels"}, ensure_ascii=False, indent=1)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
