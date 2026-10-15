## Findings (evidence-supported only)

**Common period 2011–2016.** In 2011, 2012 and 2013 the two products are
geometrically identical within the AOI (intersection/union 1.000 each year;
1,853.6 / 8.7 / 203.3 km2; legacy-only and current-only area < 0.03 km2 per
year). 2015 has no flooding in the AOI in either product. All disagreement
sits in two years:

* **2014** — legacy 236.9 km2, current 38.2 km2; intersection/union 0.16. The
  current 2014 polygons lie inside legacy 2014 polygons (99.97% of current area
  overlapped), but 198.7 km2 of legacy 2014 polygons have no current
  counterpart. Legacy 2014 polygons with zero overlap total 198.6 km2,
  so nearly all of it consists of whole missing features (including all 15
  legacy polygons ≥ 1 km2), not trimmed edges.
* **2016** — legacy 156.3 km2 (Phayao 127.4, Chiang Rai 28.9), current 0 km2
  anywhere in the AOI: the current product has no 2016 flooding in the three
  provinces.

Pooled over the six years: legacy 2,458.8 km2-years, current 2,104.4,
intersection 2,103.7 (IoU 0.855). The current product captures 85.6% of the
legacy area; the legacy product captures 99.97% of the current area. The
legacy product is **not** larger in every year: it is equal in 2011–2013 and
2015, and larger in 2014 and 2016 only.

**Temporal vs product difference.** Of the 6,387 cells flagged in M1C.1 as
"flooded only in the legacy record", **6,281 (98.3%, 1,565 km2)** were flooded
in the legacy product only during 2005–2010 (5,491 of them in 2005), i.e.
outside the current record. Only 106 cells (26.5 km2) have legacy-only
evidence inside 2011–2016 (71 only in 2011–2016, 35 in both periods). The
M1C.1 reduction in observed flooding is therefore mostly **TEMPORAL** (years
2005–2010 are not in the current record), plus a **product difference**
confined to 2014 and 2016.

**Resolution.** Disagreement is not concentrated in edge bands. Among
area-uniform sample points in legacy-only area, 0.1% lie ≤ 20 m and 0.4% lie
≤ 50 m from a same-year current polygon. Another 54% are in a year with no
current polygon at all (2016), and 25% lie > 500 m away. Where both products
report a year they share their geometry exactly, despite the stated 1:50k vs
20 m difference. **Resolution/generalisation cannot plausibly explain the
disagreement.** Whole features and a whole year are absent from the current
product. Why is not documented (see `flood-product-documentation.md`), so the
cause stays **UNEXPLAINED** at the product level.

**Spatial structure.** Common-period disagreement is clustered in the Chiang
Rai / Phayao lowlands. The largest mixed-disagreement area (185 km2) is in
Phayao near 100.03 E, 19.35 N (DSM median elevation 380 m, slope p90 1.4°,
168 m from a major waterway). There, both products agree in 2011–2013 and the
legacy product adds 2014/2016 flooding. The largest legacy-only common-period
cluster is 7 km2 (Chiang Rai, 99.95 E, 19.62 N). Current-only area is
negligible (0.76 km2, 9 cells, Chiang Mai). Lowland/basin context is
descriptive (DSM elevation and slope, waterway distance), not a cause.

**Recurrence.** Using the same six years for both products, area flooded in ≥
2 of 6 years is 292 km2 (legacy) vs 113 km2 (current), and ≥ 3 of 6 is 63 vs
5 km2. The current record's recurrence counts are lowered by the missing 2014
and 2016 features, so recurrence thresholds on the current product alone
measure that product's year coverage as much as flooding.

## Decision gate

1. **Do the products materially disagree for the same years?** Yes for 2014
   (IoU 0.16) and 2016 (current has nothing). No for 2011–2013 (identical).
   Pooled 2011–2016: 355 km2-years legacy-only vs 0.7 km2-years current-only.
2. **Can resolution/generalisation explain most of it?** No. The products
   share geometry where both report, and the disagreement consists of whole
   polygons and a whole year that are missing, mostly far from any
   counterpart.
3. **Is the newer record understood well enough to drive regional policy
   alone?** No. It omits AOI flooding that GISTDA's own legacy product records
   for 2014 and 2016, without documentation. Its 2017–2023 completeness can't
   be checked against another product.
4. **Should legacy-only flooding create a verification flag?** Yes, as
   positive evidence that can only raise concern to verification. This covers
   common-period legacy-only evidence (product disagreement, 106 cells) and
   pre-2011 legacy evidence (temporal, 6,281 cells). The two are kept as
   distinct reasons.
5. **Is a recurrence policy ready to be selected?** No. The record a
   recurrence is counted on must first be defined: the current product alone
   undercounts 2014/2016 relative to the legacy product.

## Recommended evidence policy (not implemented)

**D — annual-union record with per-year provenance, plus legacy verification
reasons.** It is a variant of C that the reconciliation supports:

* For 2011–2013 the products are identical, so a per-year union adds nothing
  and double-counts nothing. For 2014 and 2016 the union keeps the legacy
  features the current product lacks. A 2005–2023 annual record (19 years) is
  formed from legacy 2005–2010, union 2011–2016 and current 2017–2023. Every
  year keeps its source label.
* Recurrence would then be "≥ k of 19 years", re-evaluated with recurrence
  years and cell fraction as separate dimensions (`outputs/m1c2/recurrence-
  sensitivity-current.csv` gives the current-only baseline).
* Separate reason codes: `LEGACY_ONLY_COMMON_PERIOD_FLOOD` (product
  disagreement) and `LEGACY_PRE_2011_FLOOD` (temporal). Both are positive
  evidence only; legacy absence never lowers concern.

Trade-offs:

| Option | For | Against |
|---|---|---|
| A. current only, legacy informational | single documented-access product; simple | discards 2014/2016 features GISTDA itself mapped and all 2005–2010 evidence; undercounts recurrence |
| B. current primary + legacy verification flag | keeps current semantics; legacy can only raise to verification | recurrence still counted on an incomplete record; flags only, no strength |
| C. dual-source union (all years) | maximal recall | the record length and definition become implicit unless per-year provenance is kept |
| **D. per-year union with provenance (recommended)** | uses identical geometry where available, fills the 2014/2016 gaps, a 19-year explicit record, legacy reasons kept distinct | longer record changes threshold meaning again (must be re-reviewed); mixes two undocumented products |
