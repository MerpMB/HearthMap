"""Build the data bundle for the HearthMap story map (presentation layer).

Descriptive only: stacks existing M1E / M2A / M2D evidence per 500 m cell and per district.
No suitability score is computed anywhere.  Output: outputs/m2e-story/data.json
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from PIL import Image
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "m2e-story"
OUT.mkdir(parents=True, exist_ok=True)

PX = 300.0  # web-mercator pixel size in metres (cells are 500 m)
PROV_TH = {"TH50": "เชียงใหม่", "TH57": "เชียงราย", "TH56": "พะเยา"}
PROV_EN = {"TH50": "Chiang Mai", "TH57": "Chiang Rai", "TH56": "Phayao"}

# ---------------------------------------------------------------- load
haz = pd.read_parquet(ROOT / "outputs/m1e/natural-hazard-actions.parquet")
fam = pd.read_parquet(
    ROOT / "outputs/m2a/family-infrastructure-evidence.parquet",
    columns=[
        "cell_id",
        "drive_time_to_nearest_hospital_min",
        "drive_time_to_nearest_primary_school_min",
        "road_access_context",
    ],
)
ctx = pd.read_parquet(
    ROOT / "outputs/m2d/regional-context-evidence.parquet",
    columns=[
        "cell_id",
        "analysis_point_lon",
        "analysis_point_lat",
        "population_worldpop2025_mass_aoi_clipped",
        "built_ghsl2020_m2_aoi_clipped",
        "built_ghsl2020_intensity_fraction_of_nominal_grid_cell",
        "drive_time_to_nearest_service_cluster_core_min",
        "diw_factory_count_tambon_context",
    ],
)
grid = gpd.read_file(ROOT / "data/processed/m1a/grid.gpkg", columns=["cell_id", "col", "row"])
df = (
    haz[
        [
            "cell_id",
            "majority_pcode",
            "clipped_area_km2",
            "regional_search_action",
            "flood_severity",
            "landslide_severity",
            "seismic_shaking_severity",
            "natural_hazard_integrated_state",
        ]
    ]
    .merge(fam, on="cell_id")
    .merge(ctx, on="cell_id")
    .merge(pd.DataFrame(grid[["cell_id", "col", "row"]]), on="cell_id")
)
assert len(df) == 162073

# ---------------------------------------------------------------- districts
dist = gpd.read_file(ROOT / "data/processed/m1a/boundaries.gpkg", layer="district_boundaries")
dist = dist.sort_values("adm2_pcode").reset_index(drop=True)
dist["did"] = np.arange(1, len(dist) + 1)  # 0 = outside AOI

pts = gpd.GeoDataFrame(
    df[["cell_id", "majority_pcode"]],
    geometry=gpd.points_from_xy(df.analysis_point_lon, df.analysis_point_lat),
    crs=4326,
).to_crs(32647)
j = gpd.sjoin(pts, dist[["did", "adm1_pcode", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
# a cell only takes a district of its own province (M2D.1b rule); otherwise nearest own-province district
bad = j.did.isna() | (j.adm1_pcode != j.majority_pcode)
for i in j.index[bad]:
    cand = dist[dist.adm1_pcode == j.at[i, "majority_pcode"]]
    j.at[i, "did"] = cand.loc[cand.distance(j.at[i, "geometry"]).idxmin(), "did"]
df["did"] = j.did.astype(int).values
print("cells reassigned to own-province district:", int(bad.sum()))

# ---------------------------------------------------------------- per-cell codes
ACTION = {"CONTINUE_SEARCH": 1, "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION": 2, "DEPRIORITIZE_REGION": 3, "UNRESOLVED": 4}
SEV = {"NONE": 1, "VERIFY": 2, "STRONG": 3, "NOT_ASSESSED": 4, "UNRESOLVED": 4}
df["c_action"] = df.regional_search_action.map(ACTION).fillna(4).astype(np.uint8)
df["c_flood"] = df.flood_severity.map(SEV).fillna(4).astype(np.uint8)
df["c_land"] = df.landslide_severity.map(SEV).fillna(4).astype(np.uint8)
df["c_seis"] = df.seismic_shaking_severity.map(SEV).fillna(4).astype(np.uint8)


def q_min(s: pd.Series) -> np.ndarray:  # minutes, 255 = unresolved (no routed access)
    return np.where(s.isna(), 255, np.clip(np.round(s), 0, 254)).astype(np.uint8)


df["c_hosp"] = q_min(df.drive_time_to_nearest_hospital_min)
df["c_svc"] = q_min(df.drive_time_to_nearest_service_cluster_core_min)
df["c_sch"] = q_min(df.drive_time_to_nearest_primary_school_min)
pop = df.population_worldpop2025_mass_aoi_clipped.clip(lower=0)
df["c_pop"] = np.round(np.log10(1 + pop) / np.log10(1 + 3600) * 254).clip(0, 254).astype(np.uint8)
df["c_built"] = np.round(df.built_ghsl2020_intensity_fraction_of_nominal_grid_cell.clip(0, 0.5) / 0.5 * 254).astype(np.uint8)

# ---------------------------------------------------------------- mercator raster
to_merc = Transformer.from_crs(32647, 3857, always_xy=True)
from_merc_utm = Transformer.from_crs(3857, 32647, always_xy=True)
from_merc_ll = Transformer.from_crs(3857, 4326, always_xy=True)

cmin, cmax, rmin, rmax = df.col.min(), df.col.max(), df.row.min(), df.row.max()
lut = np.full((rmax - rmin + 1, cmax - cmin + 1), -1, dtype=np.int32)
lut[(df.row - rmin).values, (df.col - cmin).values] = np.arange(len(df))

x0, y0 = to_merc.transform(cmin * 500, rmin * 500)
x1, y1 = to_merc.transform((cmax + 1) * 500, (rmax + 1) * 500)
corners = [to_merc.transform(a, b) for a in (cmin * 500, (cmax + 1) * 500) for b in (rmin * 500, (rmax + 1) * 500)]
X0, X1 = min(c[0] for c in corners), max(c[0] for c in corners)
Y0, Y1 = min(c[1] for c in corners), max(c[1] for c in corners)
W, H = int((X1 - X0) / PX) + 1, int((Y1 - Y0) / PX) + 1
xs = X0 + (np.arange(W) + 0.5) * PX
ys = Y1 - (np.arange(H) + 0.5) * PX
gx, gy = np.meshgrid(xs, ys)
E, N = from_merc_utm.transform(gx.ravel(), gy.ravel())
cc = np.floor(np.asarray(E) / 500).astype(int) - cmin
rr = np.floor(np.asarray(N) / 500).astype(int) - rmin
ok = (cc >= 0) & (cc < lut.shape[1]) & (rr >= 0) & (rr < lut.shape[0])
cell_of_px = np.full(W * H, -1, dtype=np.int32)
cell_of_px[ok] = lut[rr[ok], cc[ok]]

# pixel -> district by true polygon (so the map edge follows the AOI boundary)
px_did = np.zeros(W * H, dtype=np.uint8)
E_, N_ = np.asarray(E), np.asarray(N)
for _, d in dist.iterrows():
    minx, miny, maxx, maxy = d.geometry.bounds
    m = (E_ >= minx) & (E_ <= maxx) & (N_ >= miny) & (N_ <= maxy) & (cell_of_px >= 0)
    idx = np.where(m)[0]
    inside = shapely.contains_xy(d.geometry, E_[idx], N_[idx])
    px_did[idx[inside]] = d.did
valid = (px_did > 0) & (cell_of_px >= 0)


def chan(col: str) -> np.ndarray:
    a = np.zeros(W * H, dtype=np.uint8)
    a[valid] = df[col].values[cell_of_px[valid]]
    return a.reshape(H, W)


def png_b64(r, g, b) -> str:
    im = Image.fromarray(np.dstack([r, g, b]), "RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


did_img = np.where(valid, px_did, 0).astype(np.uint8).reshape(H, W)
tiles = [
    png_b64(chan("c_action"), chan("c_flood"), chan("c_land")),
    png_b64(chan("c_seis"), chan("c_hosp"), chan("c_svc")),
    png_b64(chan("c_sch"), chan("c_pop"), chan("c_built")),
    png_b64(did_img, did_img * 0, did_img * 0),
]
# valid mask: did>0 means inside AOI; hosp etc. = 0 outside cells.  Mark cells present but 0 minutes ambiguity:
# a pixel is drawn only where did>0.

lon0, lat0 = from_merc_ll.transform(X0, Y0)
lon1, lat1 = from_merc_ll.transform(X1, Y1)

# ---------------------------------------------------------------- district statistics (cell based, AOI clipped)
def wmed(vals: pd.Series, w: pd.Series) -> float | None:
    m = vals.notna() & (w > 0)
    if not m.any():
        return None
    v, ww = vals[m].values, w[m].values
    o = np.argsort(v)
    cw = np.cumsum(ww[o])
    return float(v[o][np.searchsorted(cw, cw[-1] / 2)])


def stats(g: pd.DataFrame) -> dict:
    a = g.clipped_area_km2
    A = float(a.sum())
    P = float(g.population_worldpop2025_mass_aoi_clipped.sum())
    sh = lambda mask: round(float(a[mask].sum() / A), 4) if A else 0.0
    pop = g.population_worldpop2025_mass_aoi_clipped
    hosp, svc = g.drive_time_to_nearest_hospital_min, g.drive_time_to_nearest_service_cluster_core_min

    def pop_within(s, t):
        return round(float(pop[s.le(t)].sum() / P), 4) if P else None

    return {
        "area_km2": round(A, 1),
        "pop": int(round(P)),
        "pop_density": round(P / A, 1) if A else 0,
        "built_km2": round(float(g.built_ghsl2020_m2_aoi_clipped.sum() / 1e6), 2),
        "cells": int(len(g)),
        "act_continue": sh(g.regional_search_action == "CONTINUE_SEARCH"),
        "act_caution": sh(g.regional_search_action == "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION"),
        "act_deprio": sh(g.regional_search_action == "DEPRIORITIZE_REGION"),
        "act_unres": sh(g.regional_search_action == "UNRESOLVED"),
        "seismic_design": sh(g.seismic_shaking_severity == "STRONG"),
        "flood_strong": sh(g.flood_severity == "STRONG"),
        "flood_verify": sh(g.flood_severity == "VERIFY"),
        "landslide_strong": sh(g.landslide_severity == "STRONG"),
        "landslide_na": sh(g.landslide_severity == "NOT_ASSESSED"),
        "no_road_share": sh(g.drive_time_to_nearest_hospital_min.isna()),
        "hosp_med_pop_w": wmed(hosp, pop),
        "svc_med_pop_w": wmed(svc, pop),
        "pop_hosp_30": pop_within(hosp, 30),
        "pop_svc_30": pop_within(svc, 30),
        "pop_hosp_unres": round(float(pop[hosp.isna()].sum() / P), 4) if P else None,
        "factories_tambon_ctx": int(g.diw_factory_count_tambon_context.fillna(0).max()),
    }


recs = []
for _, d in dist.iterrows():
    g = df[df.did == d.did]
    rep = d.geometry.representative_point()
    lon, lat = Transformer.from_crs(32647, 4326, always_xy=True).transform(rep.x, rep.y)
    recs.append(
        {
            "did": int(d.did),
            "pcode": d.adm2_pcode,
            "name": d.adm2_name,
            "name_th": d.adm2_name_th,
            "prov": d.adm1_pcode,
            "prov_en": PROV_EN[d.adm1_pcode],
            "prov_th": PROV_TH[d.adm1_pcode],
            "lon": round(lon, 4),
            "lat": round(lat, 4),
            **stats(g),
        }
    )
prov_stats = []
for pc in ["TH50", "TH57", "TH56"]:
    g = df[df.majority_pcode == pc]
    prov_stats.append({"pcode": pc, "name": PROV_EN[pc], "name_th": PROV_TH[pc], **stats(g)})
total = stats(df)

# ---------------------------------------------------------------- geometry
def to_geojson(gdf: gpd.GeoDataFrame, keep: list[str], tol: float) -> dict:
    g = gdf.copy()
    g["geometry"] = g.geometry.simplify(tol, preserve_topology=True)
    g = g.to_crs(4326)
    g["geometry"] = shapely.set_precision(g.geometry.values, 0.0001)
    return json.loads(g[keep + ["geometry"]].to_json())


prov = gpd.read_file(ROOT / "data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
prov = prov.to_crs(32647)
dgj = to_geojson(dist.rename(columns={"adm2_pcode": "pcode"}), ["did", "pcode"], 150)
pgj = to_geojson(prov, [c for c in prov.columns if c.endswith("pcode")][:1], 300)

bundle = {
    "bounds": [[lat0, lon0], [lat1, lon1]],
    "size": [W, H],
    "tiles": tiles,
    "districts": recs,
    "provinces": prov_stats,
    "total": total,
    "district_geojson": dgj,
    "province_geojson": pgj,
    "meta": {
        "cells": int(len(df)),
        "pois": 5019,
        "factories_aoi": 2061,
        "integration": "M1E provisional (BALANCED + FLOOD_ANY_SOURCE); M2A routing; M2D context",
    },
}
(OUT / "data.json").write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
print("size px", W, H, "valid px", int(valid.sum()), "data.json", round((OUT / "data.json").stat().st_size / 1e6, 2), "MB")
print(json.dumps(total, indent=1))

tpl = (Path(__file__).parent / "story_template.html").read_text(encoding="utf-8")
(OUT / "index.html").write_text(tpl.replace("__DATA__", json.dumps(bundle, ensure_ascii=False)), encoding="utf-8")
print("wrote", OUT / "index.html")
