# Open questions

Status: living list. Move answered questions into the relevant doc/ADR and
delete them here.

## Family requirements (product)

1. Maximum acceptable travel time to: kindergarten/primary school, secondary
   school, an emergency-capable hospital, a supermarket/town centre?
2. Which education pathway matters — Thai public, bilingual, international?
   This changes the school layer entirely.
3. Rural/peri-urban preference: how far from a city (Chiang Mai / Chiang Rai /
   Phayao town) is "peaceful but practical"?
4. Minimum plot size and budget band (affects which areas are realistic, M4/M5).
5. Tolerance for slope (hillside views vs. construction cost and access).
6. How much weight does seasonal haze/smoke carry? Is it a scoring factor or a
   near-exclusion for some family members' health?
7. Should value potential be weighted at all for a 20–30 year home, or used
   only as a tie-breaker?

## Scoring model

8. Thresholds for each hard constraint (flood return period / observed
   frequency, landslide class, slope %, nuisance buffer distances).
9. Is weakest-link confidence too conservative once data improves (ADR-0005)?
10. Default policy for unknown hard constraints: `unresolved` (current) or
    `exclude` for the final shortlist?
11. Should `renormalize` ever be used outside exploration?
12. How to map distances/travel times to 0–100 (linear, thresholds, decay)?

## Data

13. Do usable digital landslide-susceptibility polygons exist for the three
    provinces, and at what scale?
14. Are forest-reserve, national-park and ALRO boundaries obtainable digitally,
    and are they legally reliable enough to drive exclusion?
15. Which Thai datasets are in Indian 1975, and which transformation is most
    accurate locally?
16. Is there any mapped data on piped-water coverage outside municipalities?
17. Can assessed land values be obtained in bulk?

## Spatial

18. Cells straddling province boundaries: assign to max-overlap province, or
    keep a multi-region attribute?
19. Is 500 m the right screening resolution given valley-floor flood
    variability (valleys can be narrower than a few cells)? Consider 250 m for
    hazard layers.
20. Travel-time model: OSM network with assumed speeds per road class — how to
    validate speeds for mountain roads?

## Raised by M1A (2026-10-15)

23. Register for a GISTDA API key (user action) to evaluate the 2011–2023 flood
    recurrence layer, which is more recent than the 2005–2016 layer used.
24. RFD reserve polygons touch ~80% of AOI cells (mean cell fraction 0.76) and
    overlap national parks. How should overlapping legal categories be
    presented, and which areas are already revoked/allocated (e.g. land-reform
    transfers) but still drawn as reserve?
25. GISTDA 1:50k and COD-AB disagree by up to 4.9 km along part of the Chiang
    Mai boundary — which is right there? (Inspect in QGIS against imagery.)
26. geoBoundaries ADM1 (OSM 2017) diverges strongly (sym. diff up to 12%); is it
    usable at all for validation, or should it be dropped?
27. OSM waterway completeness differs strongly between provinces (Phayao: 309
    ways) — is a DEM-derived drainage network needed for stream proximity?
28. The flood layer ends in 2016 and is satellite-observed only. What
    complementary evidence (local flood marks, DDPM records, modelled hazard)
    is needed before any flood constraint may become definitive?

## Raised by M1C (2026-10-15) — policy selection

29. Which screening profile (CONSERVATIVE / BALANCED / PERMISSIVE), if any,
    should the family adopt? ~17% of the AOI changes outcome between BALANCED
    and either neighbour, so this is a real decision, not a formality.
30. The summed High+Very High landslide rule drives ~70% of BALANCED
    `REGIONAL_DEPRIORITIZE` cells. Is "High" (not only "Very High") DMR
    susceptibility an acceptable basis for deprioritizing a region, given the
    DMR methodology is unpublished?
31. `REQUIRES_VERIFICATION` covers ~57-59% of the AOI under every profile
    (mostly terrain/landslide-medium signals). Is that useful for regional
    search, or should verification be split by kind before M2?
32. ~90% of recurrently flooded cells lie where DMR landslide susceptibility
    was not assessed (lowlands). Is "not assessed" in floodplains acceptable as
    a known gap, rather than a critical unresolved state?
33. Seismic: acquire the DMR active-fault traces (`seismic-active-faults-dmr`)
    and agree a documented seismic methodology before `hazard_resilience` may
    be scored.

## Raised by M1C.1 (2026-10-15) — flood refresh

34. The 2011-2023 record shows less observed flooding than 2005-2016 in the AOI
    (any: 2,629 vs 3,570 km2; >= 3 years: 286 vs 605 km2), and 6,387 cells have
    observed flooding only in the legacy record. Is this a real change, a
    resolution/method effect (20 m vs 1:50k), or the 2011 extreme year sitting in
    both? Should legacy-only positive evidence raise a cell to
    REQUIRES_VERIFICATION (currently context only)?
35. Is ">= 3 of 13 years" the right recurrence definition for the new record,
    or should it be recalibrated (e.g. >= 2 of 13, which flags 5.4% of the AOI
    at 10% cover vs 1.8% for >= 3)?
36. Cells that lost their only (flood) signal and lie outside DMR landslide
    coverage become UNRESOLVED (BALANCED +259 km2). Should lowland cells
    without DMR coverage be treated as a known gap rather than unresolved?

## Raised by M1C.2 (2026-10-15) — flood reconciliation

37. Why does the current GISTDA product lack most 2014 and all 2016 AOI
    flooding that the legacy product maps (2011-2013 are identical)? Ask
    GISTDA (wgs@gistda.or.th) for the method and year coverage of both.
38. Adopt the recommended per-year union record (2005-2023, 19 years, per-year
    provenance) and re-review recurrence thresholds on it?
39. Should pre-2011 legacy-only flooding (6,281 cells, mostly 2005) raise cells
    to REQUIRES_VERIFICATION, separately from common-period legacy-only
    evidence (106 cells)?

## Raised by M1C.3 (2026-10-15) — flood fusion

40. Which flood-fusion policy for regional screening? FLOOD_ANY_SOURCE is
    recommended provisionally; FLOOD_UNION_CONSERVATIVE puts 62% of low-slope
    land into strong concern (driven by a few regional flood years) and would
    need an explicit value judgement about single-event weighting.
41. Reinstate a proximity ("within ~250 m of observed flooding") verification in
    the fused ladder? Dropping it doubles the UNRESOLVED area under BALANCED
    (468 → ~988 km2) because cells beside mapped flooding outside DMR landslide
    coverage lose their flag.
42. The slope strata (<= 5 deg, 5-15 deg) are reporting aids only. What
    residential-suitability criteria will replace them in a later milestone?
43. Should legacy-only older evidence (2005-2010) ever count toward recurrence
    strength, or stay verification-only as in FLOOD_CURRENT_PRIMARY?

## Raised by M1D (2026-10-16) — seismic evidence

44. Which DMR catalogue record governs the EQ_ZONE / active-fault licence: the current
    data.dmr.go.th record (CC Attributions, no condition) or the older data.go.th records
    that carry a no-commercial/not-a-legal-reference text? Ask DMR (via the DMR
    catalogue contact) and have the stale records corrected.
45. Ask DMR for the EQ_ZONE method: PGA-to-MMI class boundaries, source model, site/Vs30
    assumptions, map scale and data year. Until then the strong state only reads off the
    zone-VII footprint (53.7% of the AOI).
46. Is a majority rule (class VII >= 50% of the cell) the right provisional trigger for
    strong seismic screening concern? Sensitivity over 10-75% changes the AOI by < 1%, so
    the open question is the semantic one, not the cut-off.
47. What site-level evidence can be obtained for shortlisted areas (geology/sediment
    thickness, Vs30, liquefaction susceptibility, building code zone) before any parcel
    decision?
48. TMD has no bulk instrumental catalogue or API. Request a structured catalogue for
    northern Thailand?

## Raised by M1E (2026-10-16) — hazard integration

49. Which integration policy translates hazard families into search actions
    (BALANCED_ACTION reference, AVOIDANCE_FIRST, VERIFICATION_FIRST)? None is clearly better;
    VERIFICATION_FIRST deprioritizes almost nothing because flood and landslide evidence rarely
    co-occur.
50. 70% of low-slope land has a critical regional evidence gap because DMR landslide
    susceptibility is not assessed there. Is a lowland-specific hazard source (e.g. DEM-derived
    drainage / flood-plain geometry) needed before the family/infrastructure model weighs
    lowland candidates?
51. How should site-verification burden (86% of the AOI needs it for at least one family) and
    seismic-design burden enter later suitability without becoming a score?
52. Who performs and records the parcel-level due diligence in the handoff checklist?

## Process

21. Who validates outputs in QGIS, and against which known places?
22. Licensing: which sources forbid redistribution of derived outputs (WDPA,
    FABDEM, Ookla)? This matters if outputs are ever shared.
