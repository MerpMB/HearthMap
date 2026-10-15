# GISTDA flood records: 2005–2016 vs 2011–2023 (M1C.1)

Both records were opened and validated; see
`outputs/m1c1/flood-2011-2023-qa.json` (new) and the M1A validation report (old).
Newer is **not** assumed to be more correct; the differences below are factual.

| Aspect | 2005–2016 (`flood-gistda-repeated-2005-2016`) | 2011–2023 (`flood-gistda-history`) |
|---|---|---|
| Role (M1C.1) | `HISTORICAL_CORROBORATION` (legacy; context columns only) | `PRIMARY_HISTORICAL_FLOOD_EVIDENCE` |
| Observation period | 2005–2016 | 2011–2023 (overlap 2011–2016) |
| Number of years | 12 (`year2005` … `year2016` flags) | 13 (`detail[]` with one value per year; all 167,804 features carry exactly 2011…2023) |
| Source-native recurrence field | `flood_freq` = number of years with observed flooding (1–9 in the AOI) | `total` = sum of the yearly `freq` values; every `freq` is 0 or 1 and `total` = Σ`freq` for every feature, so `total` = **years observed flooded** (1–7 in the AOI) |
| Methodology (published) | Satellite-observed repeated flooding, 1:50,000 product; method not documented on the service | "Flood recurrence based on the frequency of floods in 10-year period … areas that have actually been affected by floods" — the "10-year" wording does not match the 13 yearly values; sensors/thresholds not published |
| Class semantics | Count of flooded years; no hazard classes | Count of flooded years; no hazard classes |
| Geometry / scale | 1:50,000 polygons; served EPSG:3857 (stored EPSG:4326); 214,350 polygons in the AOI provinces | 20 m (publisher metadata); GeoJSON lon/lat, split by sub-district and by the query tile; 163,162 polygons intersect the AOI; API `area` = polygon area in UTM 47N |
| Geometry QA | M1A: validated, 308 repairs (negligible change) | 0 null/empty/invalid, 0 repairs, 0 duplicates, total pairwise overlap 1×10⁻⁶ m² (areas additive) |
| Coverage | National; AOI filter by province code | National; AOI requested as 124 tiles (0.2°), all answered; feature-cap check passed (quadrant re-requests give identical area per class) |
| Observed flooded area in AOI | see `outputs/m1c1/refresh-statistics.json` (`flooded_area_km2`) | 2,628.5 km² at least once; 285.7 km² in ≥ 3 of 13 years |
| Known omissions | Flash floods, cloud-covered peaks; ends 2016 | Flash floods, cloud-covered peaks; ends 2023 (2024–2026 missing) |
| Licence | Not stated on the service (© GISTDA; internal analysis only) | Open Data Common (GISTDA open-data catalogue) |
| Access | Public ArcGIS REST | Authenticated GISTDA API (project key in Git-ignored `.env.local`; never recorded) |

## Can "observed flooded ≥ 3 of 12 years" be applied to the new record?

Not mechanically. Both fields count **years in which flooding was observed**, so
an absolute years-count threshold keeps a direct reading ("flooded in at least
three separate years") on both records. But the denominators differ (12 vs 13
years), the periods differ (2005–2016 vs 2011–2023), and the scale/sensor basis
differs (1:50k vs 20 m). Therefore:

* the derived indicator is renamed and re-defined explicitly:
  `flood_years_ge{k}_area_fraction` = share of the cell observed flooded in ≥ k
  of the **13** years 2011–2023 (k = 2, 3, 4, 5);
* the evidence carries `flood_source_id`, `flood_evidence_period` and
  `flood_record_years`, and both the interpretation and the policy **refuse**
  evidence whose record differs from the configured one (tested) — no hidden
  migration of threshold meaning;
* the policy keeps k = 3 (≈ 23% of the 13 years vs 25% of 12) as the
  provisional recurrence definition and reports the full sensitivity for
  k = 2…5 × fractions 0.05/0.10/0.25/0.50 (`outputs/m1c1/policy/
  candidate-threshold-sensitivity.csv`);
* the legacy record is kept per cell as `legacy_flood_2005_2016_*` (≥ k of 12
  years), prohibited as a policy input and never read by interpretation.
