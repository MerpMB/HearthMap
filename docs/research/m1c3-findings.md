## Findings

**Ledger.** 32,621 of 162,073 cells (20.1%) have flooding mapped by at least one
GISTDA product in at least one year 2005–2023; 129,452 have none. The raw count
of mapped years per cell (`observed_year_count_total`) is 1 for 9,076 cells, 2
for 5,624, 3 for 4,782, 4 for 4,478, 5 for 4,049 and 6+ for 4,612. It is a count
of mapped years, not a probability. The mapped area is dominated by a few
regional flood years (mapped area in the AOI: 2011 1,854 km2; 2005 1,424;
2017 1,096; 2010 832; 2009 734; 2022 487). 3,057 cells carry a 2011–2016 product disagreement (2014 and 2016) that
stays visible after fusion.

**The three candidates are not equally different.** `FLOOD_CURRENT_PRIMARY` and
`FLOOD_ANY_SOURCE` differ on only 1,262 cells (315 km2, 0.8% of the AOI; 304 km2
of that is verification → strong). `FLOOD_UNION_CONSERVATIVE` is the outlier: it
adds strong concern for 18,070 cells (4,508 km2) versus 4,337 (1,079 km2) and
5,556 (1,383 km2). Its extra strong cells come from two rules: ≥ 50% of a cell
flooded in any single year (11,238 cells; the triggering years are 2011 for
5,535 cells, 2005 for 4,312, 2017 for 3,458, 2010 for 2,254, 2009 for 2,050) and ≥ 2 years of ≥ 10% anywhere in the 2005–2023 ledger
(17,207 cells, 14,192 of which include 2011: two of the big regional flood
years, not necessarily recurrence at a place).

**Flood-source choice vs hydrogeomorphic-profile choice.**

| | flood-source choice (3 candidates, profile fixed) | profile choice (3 profiles, flood policy fixed) |
|---|---|---|
| mean pairwise changed area | 2,476 km2 (6.2% of AOI) | 6,707 km2 (16.8%) |
| maximum pairwise changed area | 3,733 km2 | 9,125 km2 |
| area that is not identical across all 9 combinations | 32% of the AOI (shared) | |

Over the whole AOI the profile choice moves roughly 2.7 times more area than the
flood-source choice. But the two choices act on different land:

* On **low-slope land** (DSM slope p90 ≤ 5°, 6,026 km2, 15% of the AOI), the
  flood-source choice changes the overall outcome of 47.7% of the area, while the
  profile choice changes only 0.9% (57 km2).
* On **steep land** (> 15°, 28,146 km2, 70% of the AOI), the profile choice
  changes 30%, the flood-source choice 0.6%.
* 77% of all flood-source-sensitive area is on low-slope land (5.1× its share of
  the AOI), and 96% is ≤ 15°.

The two decisions are therefore nearly independent: profiles differ about steep
land (landslide and terrain thresholds), flood policies differ about lowlands.
The slope strata are descriptive only; nothing here says low-slope land is
suitable.

**Sensitive regions.** 3,733 km2 (14,957 cells) change outcome with the
flood-source choice under at least one profile, in 1,489 connected components;
the ten largest hold 53%. All of the leading regions show the same pattern
(REQUIRES_VERIFICATION under both current-primary and any-source, STRONG
CONCERN under the union candidate): Chiang Rai basin (507 km2, 99.77 E, 19.55 N,
82% low slope), Phayao lowland (321 km2), Chiang Mai (259 km2, 99.10 E, 18.81 N),
Chiang Rai east (186 km2) and others. Product disagreement and older-only
evidence are minor contributors there (at most 17% and 30% of the cells in each leading region); recent
2017–2023 evidence dominates.

**Behaviour checks.**

* Positive-only, nesting (current-primary ≤ any-source ≤ union) and the wording
  rules hold for all candidates (tested). No state or code claims safety.
* `FLOOD_UNION_CONSERVATIVE` puts 62% of low-slope land into strong concern, in
  effect removing the lowland search space on the strength of a few regional
  flood years. This is not an error in the rule as written, but it is the
  behaviour most in need of a value judgement and I do not recommend it as
  written.
* All fused candidates drop the previous policy's "within 250 m of observed
  flooding" verification rule (the ledger is area-based). Under BALANCED the
  UNRESOLVED area roughly doubles (468 → 988–990 km2; 848 km2 under the union
  candidate) because cells beside mapped
  flooding and outside DMR landslide coverage no longer carry a verification
  flag. This is a measurable side effect to review, not hidden.
* A flood candidate alone never reaches `REGIONAL_DEPRIORITIZE` (flood caps at
  STRONG); deprioritization comes from landslide/terrain or the multi-hazard
  escalation, so deprioritized area is nearly the same under all three
  candidates (8,181–8,186 km2 under BALANCED).

## Decision gate

1. **Is flood-policy uncertainty small enough to choose an overall hazard
   profile?** Yes for the profile decision itself, because the flood choice and
   the profile choice act on different land and are almost independent (0.9% of
   low-slope area depends on the profile; 0.6% of steep area depends on the
   flood source). The flood policy is not settled in lowlands, but that decision
   does not change which profile to prefer.
2. **Which cells remain sensitive to flood-source treatment?** 3,733 km2,
   concentrated in the Chiang Rai and Phayao basins and the Chiang Mai valley
   (see `policy-sensitive-regions.csv`), almost all of it the gap between the
   union candidate and the other two.
3. **Disproportionately inside residential lowlands?** Yes: 77% of the sensitive
   area is on ≤ 5° land, which is 15% of the AOI (ratio 5.1). Whether any of it
   is residential or suitable is not assessed.
4. **Obviously unreasonable behaviour?** None against the stated principles. Two
   behaviours need review: single-year dominance in the union candidate and the
   dropped proximity rule.
5. **Can one flood-fusion policy be recommended for regional screening?**
   `FLOOD_ANY_SOURCE` (provisionally, not selected): any well-supported
   observation raises concern, legacy evidence stays positive-only, recent and
   consensus recurrence escalate, overlap disagreement triggers verification,
   and no single regional flood year dominates. It differs from the current-
   primary candidate on only 0.8% of the AOI, so the real choice is between the
   recurrence-based pair and the union candidate.
