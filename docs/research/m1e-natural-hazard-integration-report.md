# HearthMap M1E - Natural Hazard policy integration

> Committed copy of `outputs/m1e-review/README.md`; images and tables live in the untracked review folder.

**Hazard integration 0.1.0 - PROVISIONAL; regional screening only; no scalar hazard score; no integration policy selected.** Inputs: `hydrogeomorphic_profile = BALANCED`, `flood_fusion_policy = FLOOD_ANY_SOURCE` (`selected_for_provisional_screening = true`, `production_truth = false`) and the experimental M1D seismic evidence. Parcel/site hazard assessment is NOT complete and ground response is not assessed anywhere. Semantics: `docs/product/natural-hazard-integration.md`.

## Findings (M1E v0.1.0, regional screening; PROVISIONAL)

**Integration state (AOI).** The dimension-preserving summary spreads the area over the
action types rather than along one scale:

| Integrated state | Area | Share |
|---|---:|---:|
| `NO_MAJOR_ACTION_TRIGGERED` | 2,394 km² | 6.0% |
| `VERIFY_SITE` | 10,322 km² | 25.9% |
| `ENGINEERING_MITIGATION_REQUIRED` | 15,513 km² | 38.9% |
| `STRONG_AVOIDANCE_SIGNAL` | 5,534 km² | 13.9% |
| `MULTIPLE_ACTIONS` (avoidance + mitigation) | 5,924 km² | 14.8% |
| `UNRESOLVED` (hydrogeomorphic evidence) | 244 km² | 0.6% |

**Provinces (share of province area; descriptive, no province is called safer).**

| Measure | Chiang Mai | Phayao | Chiang Rai |
|---|---:|---:|---:|
| avoidance signal (flood or landslide) | 32.1% | 16.1% | 28.9% |
| `DEPRIORITIZE_REGION` (reference mapping) | 26.3% | 8.2% | 16.0% |
| continue with avoidance caution | 5.8% | 7.9% | 12.9% |
| site verification required | 84.8% | 73.7% | 95.2% |
| engineering mitigation required | 50.7% | 24.0% | 75.2% |
| multiple actions | 14.8% | 3.2% | 21.0% |
| critical regional evidence gap | 6.1% | 21.0% | 19.3% |
| no major action triggered | 6.6% | 15.1% | 0.0% |

Chiang Mai's avoidance is almost entirely landslide-driven (31.7% of the province;
flood 0.4%); Chiang Rai has the most flood avoidance (8.5%, plus 20.5% landslide) and by far
the largest seismic-design area; Phayao has the least avoidance (flood 5.0%, landslide
11.1%) and the least seismic design, but 23.8% of its area lacks landslide assessment
(Chiang Rai 22.4%, Chiang Mai 6.8%). These are different burdens, not a ranking.

**Avoidance signals.** 11,458 km² (28.7%) carry a flood or landslide avoidance signal; under
the reference mapping 8,182 km² (20.5%) is deprioritized and 3,275 km² (8.2%) continues with
avoidance caution. On low-slope land only 0.1% is deprioritized (20.4% continues with
caution), against 28.9% on steep land: avoidance is mostly an upland/landslide matter,
lowland flood evidence mostly gives caution and verification. Seismic evidence never enters
this axis.

**Verification burden (corrected in M1E.1).** 86.1% of the AOI (34,377 km²) is flagged
`VERIFY_SITE_REQUIRED`. The M1E report quoted a trigger distribution that summed to 100% but
implied only 80.9% with at least one trigger. Cause: the two numbers described different
populations, both by area. The flag also fires where the seismic screening state alone
requires verification (a nearby recorded M ≥ 5 event, which the history family reports as
`CONTEXT_ONLY`): 8,502 cells, 2,072 km² (5.2% of the AOI), which the old count did not
attribute to any trigger. Neither percentage was wrong; the count omitted a population. The
count now includes that trigger (`seismic_state`), so *flag ⇔ triggers ≥ 1*. Policy
semantics and every action area are unchanged. Corrected distribution (share of AOI area):
0 triggers 13.9%, 1: 49.5%, 2: 30.4%, 3: 6.2%, 4: 0.03% (sums to 100%; ≥ 1 = 86.1%).
The burden is broad, so it discriminates little on its own; its value is in naming *which*
information is needed.

**Engineering mitigation.** 21,436 km² (53.7%) requires seismic design (Chiang Rai 75.2%,
Chiang Mai 50.7%, Phayao 24.0%; low-slope land 63.2%). This does not remove land from the
search.

**Hydrogeomorphic × seismic.** Hydrogeomorphic "favourable" with seismic strong covers
**3,349 km² (8.4%)** (M1D figure reproduced): Chiang Mai 1,900 km² (8.6% of the province),
Chiang Rai 1,048 km² (9.1%), Phayao 401 km² (6.5%). It sits mostly on steeper land: low-
slope 280 km² (8%), gentle 5–15° 1,364 km² (41%), steep 1,704 km² (51%), median DSM
elevation 452 m. It is fragmented (1,170 components, largest 373 km², the five largest hold
35%), lies 64.5% within 5 km of a mapped fault trace (47% nearest the Mae Tha group) and is
100% driven by zone VII dominance; the landslide evidence is assessed everywhere and flood
evidence is 89% "no major observed signal". 87% still needs site verification. These areas
are **not unsuitable**: they are searchable and need seismic design and site-response work.
Other combinations (AOI area): hydro verification + seismic strong 11,421 km² (28.6%); hydro
strong concern + seismic strong 1,702 km² (4.3%); hydro deprioritize + seismic strong
4,222 km² (10.6%, almost all steep, retained as deprioritized); hydro unresolved + seismic
strong 744 km² (1.9%, mostly low-slope); hydro favourable + seismic verification 705 km²
(1.8%); both none detected 2,394 km² (6.0%); hydro deprioritize + seismic none detected
2,467 km² (6.2%, still deprioritized).

**Unresolved evidence.** Landslide susceptibility is not assessed by DMR for 5,581 km²
(14.0%), and these cells are concentrated in the lowlands: 70.2% of low-slope land has a
critical regional evidence gap (22.3% complete), against 0.1% of steep land. Ground response
is not assessed in any cell. The regional search action is unresolved for 988 km² (2.5%,
10.8% of low-slope land).

**Integration-policy sensitivity (nothing selected).** Deprioritized area: `BALANCED_ACTION`
8,182 km² (20.5%), `AVOIDANCE_FIRST` 11,458 km² (28.7%; +3,275 km² over the reference),
`VERIFICATION_FIRST` 4 km² (~0%). `VERIFICATION_FIRST` deprioritizes almost nothing because
its condition (flood **and** landslide avoidance in one cell) is almost never met: flood
evidence lies in the lowlands and assessed landslide evidence in the uplands. None of the
three is clearly better under the stated principles: `AVOIDANCE_FIRST` adds an avoidance
rule the selected hydrogeomorphic policy did not adopt, and `VERIFICATION_FIRST` effectively
removes avoidance. `BALANCED_ACTION` is used as the *reference mapping* only because it adds
no rule beyond the already selected policy; it is not selected.

**Recommendation basis.** The integration preserves every family's evidence, keeps
avoidance, verification, mitigation and uncertainty distinct, never lets seismic results
deprioritize or cancel hydrogeomorphic evidence, and is tested for these properties. The main
open issue for the next model is the lowland landslide-coverage gap, which leaves most
realistic home-search land with a critical regional evidence gap.


## Action areas by province (cells in the artifact; area / share of scope)

| measure | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| avoidance_signal | 11,458 km2 (28.7%) | 7,113 km2 (32.1%) | 995 km2 (16.1%) | 3,349 km2 (28.9%) |
| regional_search_deprioritize_region (BALANCED_ACTION reference) | 8,182 km2 (20.5%) | 5,821 km2 (26.3%) | 508 km2 (8.2%) | 1,853 km2 (16.0%) |
| regional_search_continue_with_avoidance_caution | 3,275 km2 (8.2%) | 1,292 km2 (5.8%) | 487 km2 (7.9%) | 1,496 km2 (12.9%) |
| regional_search_unresolved | 988 km2 (2.5%) | 515 km2 (2.3%) | 172 km2 (2.8%) | 300 km2 (2.6%) |
| site_verification_required | 34,377 km2 (86.1%) | 18,795 km2 (84.8%) | 4,566 km2 (73.7%) | 11,016 km2 (95.2%) |
| engineering_mitigation_required | 21,436 km2 (53.7%) | 11,238 km2 (50.7%) | 1,487 km2 (24.0%) | 8,711 km2 (75.2%) |
| multiple_actions_state | 5,924 km2 (14.8%) | 3,289 km2 (14.8%) | 199 km2 (3.2%) | 2,436 km2 (21.0%) |
| partial_regional_evidence | 716 km2 (1.8%) | 172 km2 (0.8%) | 177 km2 (2.8%) | 367 km2 (3.2%) |
| critical_regional_gap | 4,884 km2 (12.2%) | 1,349 km2 (6.1%) | 1,301 km2 (21.0%) | 2,234 km2 (19.3%) |
| no_major_action_triggered | 2,394 km2 (6.0%) | 1,459 km2 (6.6%) | 935 km2 (15.1%) | 0 km2 (0.0%) |

## Integrated action state

| state | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| NO_MAJOR_ACTION_TRIGGERED | 2,394 km2 (6.0%) | 1,459 km2 (6.6%) | 935 km2 (15.1%) | 0 km2 (0.0%) |
| VERIFY_SITE | 10,322 km2 (25.8%) | 5,564 km2 (25.1%) | 2,870 km2 (46.3%) | 1,889 km2 (16.3%) |
| ENGINEERING_MITIGATION_REQUIRED | 15,513 km2 (38.8%) | 7,949 km2 (35.9%) | 1,289 km2 (20.8%) | 6,275 km2 (54.2%) |
| STRONG_AVOIDANCE_SIGNAL | 5,534 km2 (13.9%) | 3,825 km2 (17.3%) | 796 km2 (12.8%) | 913 km2 (7.9%) |
| MULTIPLE_ACTIONS | 5,924 km2 (14.8%) | 3,289 km2 (14.8%) | 199 km2 (3.2%) | 2,436 km2 (21.0%) |
| UNRESOLVED | 244 km2 (0.6%) | 74 km2 (0.3%) | 106 km2 (1.7%) | 64 km2 (0.5%) |

![multiple-hazard-actions.png](../../outputs/m1e-review/multiple-hazard-actions.png)

## Regional search action under three integration policies

| scope | search_action | BALANCED_ACTION | AVOIDANCE_FIRST | VERIFICATION_FIRST |
|---|---|---|---|---|
| AOI | CONTINUE_SEARCH | 27,485 km2 (68.8%) | 27,485 km2 (68.8%) | 27,485 km2 (68.8%) |
| AOI | CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION | 3,275 km2 (8.2%) | 0 km2 (0.0%) | 11,454 km2 (28.7%) |
| AOI | DEPRIORITIZE_REGION | 8,182 km2 (20.5%) | 11,458 km2 (28.7%) | 4 km2 (0.0%) |
| AOI | UNRESOLVED | 988 km2 (2.5%) | 988 km2 (2.5%) | 988 km2 (2.5%) |
| Chiang Mai | CONTINUE_SEARCH | 14,531 km2 (65.6%) | 14,531 km2 (65.6%) | 14,531 km2 (65.6%) |
| Chiang Mai | CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION | 1,292 km2 (5.8%) | 0 km2 (0.0%) | 7,113 km2 (32.1%) |
| Chiang Mai | DEPRIORITIZE_REGION | 5,821 km2 (26.3%) | 7,113 km2 (32.1%) | 0 km2 (0.0%) |
| Chiang Mai | UNRESOLVED | 515 km2 (2.3%) | 515 km2 (2.3%) | 515 km2 (2.3%) |
| Phayao | CONTINUE_SEARCH | 5,027 km2 (81.2%) | 5,027 km2 (81.2%) | 5,027 km2 (81.2%) |
| Phayao | CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION | 487 km2 (7.9%) | 0 km2 (0.0%) | 995 km2 (16.1%) |
| Phayao | DEPRIORITIZE_REGION | 508 km2 (8.2%) | 995 km2 (16.1%) | 0 km2 (0.0%) |
| Phayao | UNRESOLVED | 172 km2 (2.8%) | 172 km2 (2.8%) | 172 km2 (2.8%) |
| Chiang Rai | CONTINUE_SEARCH | 7,927 km2 (68.5%) | 7,927 km2 (68.5%) | 7,927 km2 (68.5%) |
| Chiang Rai | CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION | 1,496 km2 (12.9%) | 0 km2 (0.0%) | 3,346 km2 (28.9%) |
| Chiang Rai | DEPRIORITIZE_REGION | 1,853 km2 (16.0%) | 3,349 km2 (28.9%) | 4 km2 (0.0%) |
| Chiang Rai | UNRESOLVED | 300 km2 (2.6%) | 300 km2 (2.6%) | 300 km2 (2.6%) |

Cells whose search action differs between policies:

| policy_a | policy_b | cells_changed | area_changed_km2 | share_of_aoi |
|---|---|---|---|---|
| BALANCED_ACTION | AVOIDANCE_FIRST | 13204 | 3275.3 | 0.082 |
| BALANCED_ACTION | VERIFICATION_FIRST | 33764 | 8178.5 | 0.2048 |
| AVOIDANCE_FIRST | VERIFICATION_FIRST | 46968 | 11453.9 | 0.2868 |

![natural-hazard-search-action.png](../../outputs/m1e-review/natural-hazard-search-action.png)

## Decision axes (AOI, % of stratum area; strata are reporting only)

| axis | value | ALL | LOW_SLOPE_LE_5 | GENTLE_5_15 | LOW_OR_GENTLE_LE_15 | STEEP_GT_15 |
|---|---|---|---|---|---|---|
| regional_search_action | CONTINUE_SEARCH | 68.8 | 68.7 | 90.4 | 79.3 | 64.4 |
| regional_search_action | CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION | 8.2 | 20.4 | 3.3 | 12.0 | 6.6 |
| regional_search_action | DEPRIORITIZE_REGION | 20.5 | 0.1 | 0.8 | 0.4 | 28.9 |
| regional_search_action | UNRESOLVED | 2.5 | 10.8 | 5.6 | 8.2 | 0.0 |
| site_verification_action | NONE_TRIGGERED | 13.9 | 12.5 | 23.2 | 17.7 | 12.3 |
| site_verification_action | VERIFY_SITE_REQUIRED | 86.1 | 87.5 | 76.8 | 82.3 | 87.7 |
| engineering_mitigation_action | NONE_TRIGGERED | 46.3 | 36.8 | 46.8 | 41.7 | 48.3 |
| engineering_mitigation_action | SEISMIC_DESIGN_REQUIRED | 53.7 | 63.2 | 53.2 | 58.3 | 51.7 |
| data_completeness | REGIONAL_COMPLETE_SITE_RESPONSE_MISSING | 86.0 | 22.3 | 84.8 | 52.8 | 99.9 |
| data_completeness | PARTIAL_REGIONAL_EVIDENCE | 1.8 | 7.5 | 4.1 | 5.9 | 0.1 |
| data_completeness | CRITICAL_REGIONAL_GAP | 12.2 | 70.2 | 11.1 | 41.3 | 0.1 |

Per-family recommended actions (AOI, % of area):

| family | NO_MAJOR_ACTION_TRIGGERED | STRONG_AVOIDANCE_SIGNAL | VERIFY_SITE | UNRESOLVED | ENGINEERING_MITIGATION_REQUIRED | CONTEXT_ONLY |
|---|---|---|---|---|---|---|
| flood | 83.1 | 3.5 | 13.4 | 0.0 | 0.0 | 0.0 |
| landslide | 21.7 | 25.2 | 39.1 | 14.0 | 0.0 | 0.0 |
| terrain | 74.4 | 0.0 | 25.6 | 0.0 | 0.0 | 0.0 |
| seismic_shaking | 46.0 | 0.0 | 0.3 | 0.0 | 53.7 | 0.0 |
| fault_context | 54.8 | 0.0 | 45.2 | 0.0 | 0.0 | 0.0 |
| historical_seismicity | 40.0 | 0.0 | 0.0 | 0.0 | 0.0 | 60.0 |

Verification triggers per cell (% of scope area; triggers >= 1 equals the area flagged VERIFY_SITE_REQUIRED):

| verification_triggers | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| 0 | 13.9 | 15.2 | 26.3 | 4.8 |
| 1 | 49.5 | 49.1 | 53.3 | 48.1 |
| 2 | 30.4 | 29.3 | 19.1 | 38.7 |
| 3 | 6.2 | 6.4 | 1.3 | 8.3 |
| 4 | 0.0 | 0.0 | 0.0 | 0.1 |
| 5 | 0.0 | 0.0 | 0.0 | 0.0 |
| 6 | 0.0 | 0.0 | 0.0 | 0.0 |
| 7 | 0.0 | 0.0 | 0.0 | 0.0 |

![verification-burden.png](../../outputs/m1e-review/verification-burden.png)

![engineering-mitigation.png](../../outputs/m1e-review/engineering-mitigation.png)

## Cross-family combinations

| combo | cells | area_km2 | share_of_aoi | Chiang Mai_km2 | Phayao_km2 | Chiang Rai_km2 | LOW_SLOPE_LE_5_km2 | GENTLE_5_15_km2 | STEEP_GT_15_km2 |
|---|---|---|---|---|---|---|---|---|---|
| hydro favourable + seismic strong | 13499 | 3348.5 | 0.0839 | 1900.0 | 400.8 | 1047.7 | 280.1 | 1364.3 | 1704.2 |
| hydro requires verification + seismic strong | 46040 | 11420.8 | 0.286 | 5608.2 | 822.1 | 4990.5 | 2414.0 | 1333.3 | 7673.5 |
| hydro strong concern + seismic strong | 6839 | 1702.0 | 0.0426 | 651.4 | 63.7 | 986.9 | 612.8 | 111.2 | 978.0 |
| hydro deprioritize + seismic strong | 17386 | 4221.5 | 0.1057 | 2637.3 | 135.0 | 1449.2 | 3.6 | 20.5 | 4197.4 |
| hydro unresolved + seismic strong | 3106 | 743.5 | 0.0186 | 441.1 | 65.8 | 236.6 | 497.9 | 235.4 | 10.2 |
| hydro favourable + seismic verification | 2829 | 704.8 | 0.0177 | 208.6 | 169.3 | 326.9 | 51.8 | 307.5 | 345.5 |
| hydro favourable + seismic none detected | 9631 | 2393.9 | 0.06 | 1459.3 | 934.6 | 0.0 | 237.1 | 1019.5 | 1137.2 |
| hydro deprioritize + seismic none detected | 10174 | 2466.8 | 0.0618 | 2133.1 | 333.7 | 0.0 | 0.5 | 14.3 | 2451.9 |

| combo | components | isolated_single_cells | largest_component_km2 | share_area_in_largest_5 |
|---|---|---|---|---|
| hydro favourable + seismic strong | 1170 | 366 | 372.5 | 0.352 |
| hydro requires verification + seismic strong | 1173 | 344 | 2307.1 | 0.649 |
| hydro strong concern + seismic strong | 2096 | 692 | 191.8 | 0.246 |
| hydro deprioritize + seismic strong | 1007 | 19 | 595.8 | 0.392 |
| hydro unresolved + seismic strong | 512 | 283 | 182.8 | 0.364 |
| hydro favourable + seismic verification | 374 | 137 | 89.8 | 0.268 |
| hydro favourable + seismic none detected | 697 | 176 | 700.8 | 0.557 |
| hydro deprioritize + seismic none detected | 676 | 22 | 590.8 | 0.431 |

Largest regions per combination:

| combo | rank | area_km2 | cells | lon | lat | majority_province |
|---|---|---|---|---|---|---|
| hydro favourable + seismic strong | 1 | 372.5 | 1490 | 98.991 | 19.067 | Chiang Mai |
| hydro favourable + seismic strong | 2 | 299.8 | 1199 | 98.768 | 18.577 | Chiang Mai |
| hydro favourable + seismic strong | 3 | 202.8 | 811 | 98.989 | 19.414 | Chiang Mai |
| hydro favourable + seismic strong | 4 | 160.0 | 640 | 99.184 | 19.208 | Chiang Mai |
| hydro favourable + seismic strong | 5 | 143.4 | 575 | 99.973 | 18.994 | Phayao |
| hydro requires verification + seismic strong | 1 | 2307.1 | 9254 | 99.655 | 19.493 | Chiang Rai |
| hydro requires verification + seismic strong | 2 | 1871.5 | 7548 | 100.286 | 19.985 | Chiang Rai |
| hydro requires verification + seismic strong | 3 | 1181.5 | 4726 | 98.738 | 18.863 | Chiang Mai |
| hydro requires verification + seismic strong | 4 | 1133.0 | 4580 | 99.146 | 18.895 | Chiang Mai |
| hydro requires verification + seismic strong | 5 | 915.0 | 3660 | 99.102 | 19.384 | Chiang Mai |
| hydro strong concern + seismic strong | 1 | 191.8 | 767 | 99.971 | 20.011 | Chiang Rai |
| hydro strong concern + seismic strong | 2 | 79.5 | 318 | 99.913 | 20.239 | Chiang Rai |
| hydro strong concern + seismic strong | 3 | 66.2 | 265 | 99.299 | 20.0 | Chiang Mai |
| hydro strong concern + seismic strong | 4 | 41.8 | 167 | 100.27 | 19.925 | Chiang Rai |
| hydro strong concern + seismic strong | 5 | 40.2 | 161 | 99.798 | 19.512 | Chiang Rai |
| hydro deprioritize + seismic strong | 1 | 595.8 | 2464 | 98.717 | 19.284 | Chiang Mai |
| hydro deprioritize + seismic strong | 2 | 591.8 | 2436 | 99.342 | 19.068 | Chiang Mai |
| hydro deprioritize + seismic strong | 3 | 182.2 | 729 | 98.788 | 19.532 | Chiang Mai |
| hydro deprioritize + seismic strong | 4 | 148.8 | 595 | 99.577 | 19.858 | Chiang Rai |
| hydro deprioritize + seismic strong | 5 | 137.8 | 551 | 99.497 | 20.001 | Chiang Rai |
| hydro unresolved + seismic strong | 1 | 182.8 | 750 | 98.999 | 18.747 | Chiang Mai |
| hydro unresolved + seismic strong | 2 | 25.5 | 102 | 99.834 | 19.907 | Chiang Rai |
| hydro unresolved + seismic strong | 3 | 21.2 | 85 | 99.171 | 19.91 | Chiang Mai |
| hydro unresolved + seismic strong | 4 | 20.8 | 94 | 100.195 | 20.294 | Chiang Rai |
| hydro unresolved + seismic strong | 5 | 20.0 | 80 | 98.821 | 18.591 | Chiang Mai |
| hydro favourable + seismic verification | 1 | 89.8 | 359 | 99.902 | 19.339 | Phayao |
| hydro favourable + seismic verification | 2 | 39.0 | 156 | 100.037 | 19.592 | Chiang Rai |
| hydro favourable + seismic verification | 3 | 21.5 | 86 | 99.902 | 19.479 | Chiang Rai |
| hydro favourable + seismic verification | 4 | 20.5 | 82 | 99.878 | 20.394 | Chiang Rai |
| hydro favourable + seismic verification | 5 | 18.2 | 73 | 99.007 | 19.641 | Chiang Mai |
| hydro favourable + seismic none detected | 1 | 700.8 | 2815 | 98.682 | 18.01 | Chiang Mai |
| hydro favourable + seismic none detected | 2 | 379.2 | 1517 | 100.243 | 19.118 | Phayao |
| hydro favourable + seismic none detected | 3 | 131.0 | 524 | 100.405 | 19.219 | Phayao |
| hydro favourable + seismic none detected | 4 | 73.8 | 295 | 98.602 | 18.254 | Chiang Mai |
| hydro favourable + seismic none detected | 5 | 47.5 | 190 | 98.481 | 17.386 | Chiang Mai |
| hydro deprioritize + seismic none detected | 1 | 590.8 | 2363 | 98.493 | 18.592 | Chiang Mai |
| hydro deprioritize + seismic none detected | 2 | 231.1 | 953 | 98.242 | 18.552 | Chiang Mai |
| hydro deprioritize + seismic none detected | 3 | 112.6 | 482 | 98.516 | 17.48 | Chiang Mai |
| hydro deprioritize + seismic none detected | 4 | 69.2 | 301 | 98.137 | 18.718 | Chiang Mai |
| hydro deprioritize + seismic none detected | 5 | 58.3 | 248 | 98.19 | 18.96 | Chiang Mai |

![hydro-vs-seismic.png](../../outputs/m1e-review/hydro-vs-seismic.png)

## Unresolved evidence (% of scope area)

| unresolved | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| landslide not assessed (DMR coverage) | 14.0 | 6.8 | 23.8 | 22.4 |
| terrain support insufficient | 0.0 | 0.0 | 0.0 | 0.0 |
| seismic zones not assessed | 0.0 | 0.0 | 0.0 | 0.0 |
| regional search action unresolved | 2.5 | 2.3 | 2.8 | 2.6 |
| ground response not assessed (all cells) | 100.0 | 100.0 | 100.0 | 100.0 |

![unresolved-hazard-evidence.png](../../outputs/m1e-review/unresolved-hazard-evidence.png)

## Parcel handoff profiles (cell action profile -> checklist; nothing is checked in M1E)

| parcel_handoff_checklist | cells | area_km2 | checklist_items |
|---|---|---|---|
| inspect_slope_and_retaining_conditions\|review_local_landslide_susceptibility_and_scars\|verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|evaluate_seismic_structural_requirements\|assess_liquefaction_and_site_amplification_where_relevant\|parcel_specific_site_response_investigation | 51564 | 12684.8 | 7 |
| inspect_slope_and_retaining_conditions\|review_local_landslide_susceptibility_and_scars\|parcel_specific_site_response_investigation | 50152 | 12286.8 | 3 |
| verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|evaluate_seismic_structural_requirements\|assess_liquefaction_and_site_amplification_where_relevant\|parcel_specific_site_response_investigation | 16605 | 4092.1 | 5 |
| verify_historical_local_flooding\|obtain_local_flood_history\|check_road_and_drainage_elevation\|verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|evaluate_seismic_structural_requirements\|assess_liquefaction_and_site_amplification_where_relevant\|parcel_specific_site_response_investigation | 15598 | 3887.9 | 8 |
| parcel_specific_site_response_investigation | 13312 | 3300.6 | 1 |
| verify_historical_local_flooding\|obtain_local_flood_history\|check_road_and_drainage_elevation\|parcel_specific_site_response_investigation | 8856 | 2207.3 | 4 |
| verify_historical_local_flooding\|obtain_local_flood_history\|check_road_and_drainage_elevation\|inspect_slope_and_retaining_conditions\|review_local_landslide_susceptibility_and_scars\|verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|evaluate_seismic_structural_requirements\|assess_liquefaction_and_site_amplification_where_relevant\|parcel_specific_site_response_investigation | 1582 | 394.9 | 10 |
| inspect_slope_and_retaining_conditions\|verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|evaluate_seismic_structural_requirements\|assess_liquefaction_and_site_amplification_where_relevant\|parcel_specific_site_response_investigation | 1499 | 371.3 | 6 |
| inspect_slope_and_retaining_conditions\|parcel_specific_site_response_investigation | 1110 | 273.4 | 2 |
| verify_historical_local_flooding\|obtain_local_flood_history\|check_road_and_drainage_elevation\|inspect_slope_and_retaining_conditions\|review_local_landslide_susceptibility_and_scars\|parcel_specific_site_response_investigation | 770 | 192.3 | 6 |
| inspect_slope_and_retaining_conditions\|review_local_landslide_susceptibility_and_scars\|verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|parcel_specific_site_response_investigation | 545 | 124.3 | 5 |
| verify_historical_local_flooding\|obtain_local_flood_history\|check_road_and_drainage_elevation\|verify_fault_and_site_geology\|assess_soil_and_geotechnical_conditions\|parcel_specific_site_response_investigation | 221 | 55.2 | 6 |

Characterisation of hydrogeomorphic favourable + seismic strong: see `outputs/m1e-review/integration-statistics.json` (area 3,348 km2).

## Human QA

| gate | status |
|---|---|
| M1A1_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1B_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1C_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C1_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C2_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C3_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1D_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1E_HUMAN_VISUAL_SIGNOFF | PENDING |

No review of the M1C-M1E map packs has been reported; none is inferred.

## Files

| File | Bytes |
|---|---:|
| action-axis-distribution.csv | 7,082 |
| cross-family-combinations.csv | 889 |
| cross-family-component-summary.csv | 567 |
| cross-family-largest-regions.csv | 3,103 |
| engineering-mitigation.png | 102,463 |
| example-cells.md | 4,078 |
| family-action-distribution.csv | 4,062 |
| hydro-vs-seismic.png | 153,066 |
| integrated-state-distribution.csv | 2,622 |
| integration-policy-comparison.csv | 3,460 |
| integration-policy-differences.csv | 228 |
| integration-statistics.json | 3,557 |
| multiple-hazard-actions.png | 164,350 |
| natural-hazard-search-action.png | 272,812 |
| parcel-handoff-profiles.csv | 4,123 |
| province-action-areas.csv | 2,617 |
| unresolved-evidence.csv | 1,164 |
| unresolved-hazard-evidence.png | 114,539 |
| verification-burden-distribution.csv | 798 |
| verification-burden.png | 175,541 |
| m1e/natural-hazard-actions.parquet | 2,569,524 |
| m1e/natural-hazard-actions.parquet.provenance.json | 4,814 |
