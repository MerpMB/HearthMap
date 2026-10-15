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

## Process

21. Who validates outputs in QGIS, and against which known places?
22. Licensing: which sources forbid redistribution of derived outputs (WDPA,
    FABDEM, Ookla)? This matters if outputs are ever shared.
