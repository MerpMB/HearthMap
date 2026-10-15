# Flood evidence fusion v0.1 (M1C.3)

Status: **PROVISIONAL**, no candidate selected. Config:
[`config/flood-fusion.yaml`](../../config/flood-fusion.yaml); code:
`hearthmap.hazard.flood_fusion`. Scope: hydrogeomorphic flood *screening* from two
GISTDA observed-flood products; see
[natural-hazard-scope.md](natural-hazard-scope.md).

## The ledger is observational, not a homogeneous series

Per cell and year 2005–2023 the ledger keeps the source-native flooded fractions
(`legacy_fraction`, `current_fraction`), their intersection and
legacy/current-only shares in the common years, the fused union
(`observed_flood_fraction`), an agreement state, `sources_available` and
`sources_positive`.

| Years | Sources | Agreement states |
|---|---|---|
| 2005–2010 | legacy only | `OBSERVED_SINGLE_SOURCE_LEGACY`, `NOT_OBSERVED_SINGLE_SOURCE` |
| 2011–2016 | both | `OBSERVED_CONSENSUS`, `OBSERVED_LEGACY_ONLY_OVERLAP`, `OBSERVED_CURRENT_ONLY_OVERLAP`, `OBSERVED_OVERLAP_MIXED_DISAGREEMENT`, `NOT_OBSERVED_CONSENSUS` |
| 2017–2023 | current only | `OBSERVED_SINGLE_SOURCE_CURRENT`, `NOT_OBSERVED_SINGLE_SOURCE` |

Neither product documents its methodology, so the 19 years are **not** one
homogeneous series. `observed_year_count_total` = the number of calendar years in
which at least one available GISTDA product mapped observed flooding (≥ 1% of the
cell); it is a raw observational count, **not** a probability, return period or
"k of 19" recurrence. "NOT_OBSERVED" means no polygon was mapped, never "did not
flood". The union is used for spatial screening, but product disagreement
(2011–2016) is kept as `OBSERVED_*_OVERLAP` / `has_overlap_product_disagreement`
and the years in `overlap_disagreement_years`.

Per-cell summaries: era counts (`legacy_era_observed_years`,
`overlap_consensus_observed_years`, `overlap_disagreement_observed_years`,
`current_era_observed_years`), `most_recent_observed_year`,
`oldest_observed_year`, `years_since_most_recent_observation` (from 2023, the end
of the newest record), `max_annual_flood_fraction`, era maxima and
`most_recent_observed_band` (RECENT 2017–2023, MID 2011–2016, OLDER 2005–2010).
No decay weights exist; old evidence is neither removed nor discounted.

## Flood ladder (screening terms only)

`NO_MAJOR_OBSERVED_SIGNAL` < `HISTORICAL_SIGNAL` <
`REQUIRES_FLOOD_VERIFICATION` < `STRONG_FLOOD_SCREENING_CONCERN`, plus
`UNRESOLVED` (cell not evaluated). `NO_MAJOR_OBSERVED_SIGNAL` means no mapped
flooding in either product in any year — it is never "no flood risk" or "safe".
Rules are **positive-only**: a rule can raise concern, never lower it, and no
source acts as negative evidence by lacking a polygon. A cell-year counts toward a
rule when the named metric is ≥ the rule's cell fraction; years × cell fraction
are separate dimensions. Rules, thresholds and reason codes are in the config;
thresholds follow evidence semantics and were not fitted to earlier affected-area
percentages.

## Candidates (none selected; nested by construction)

| Candidate | Idea | Strong concern if … | Verification if … |
|---|---|---|---|
| `FLOOD_CURRENT_PRIMARY` | current product primary; legacy-only observations are verification flags | current product ≥ 10% of the cell in ≥ 3 years of 2011–2023 | current ≥ 5% in a year; legacy-only ≥ 10% (2005–2010, or 2011–2016 where only legacy maps it); 2011–2016 mismatch ≥ 10% |
| `FLOOD_ANY_SOURCE` (extends the above) | any well-supported observation can raise concern; recent recurrence escalates | observed ≥ 10% in ≥ 2 years of 2017–2023; both products agree on ≥ 10% in ≥ 2 years of 2011–2016 | observed ≥ 5% in 2011–2023; ≥ 10% in 2005–2010; mismatch ≥ 5% |
| `FLOOD_UNION_CONSERVATIVE` (extends the above) | spatial union of positive evidence drives search screening | observed ≥ 10% in ≥ 2 years of 2005–2023, or ≥ 50% in one year | observed ≥ 5% any year; mismatch ≥ 1% |

`HISTORICAL_SIGNAL` (any observed ≥ 1%) is informational for the overall policy.
A flood candidate caps at STRONG: flooding alone never produces
`REGIONAL_DEPRIORITIZE`; the multi-hazard escalation of each hydrogeomorphic
profile still applies.

## Integration

`apply_policy(..., flood_override=to_policy_override(result))` replaces only the
profile's flood rule; landslide, terrain, completeness and multi-hazard logic are
unchanged. Slope strata (`LOW_SLOPE_LE_5`, `GENTLE_5_15`, `STEEP_GT_15`) are for
reporting only: `lowland_stratum` / `slope_stratum` are prohibited policy inputs,
never a hazard state and never a suitability criterion. The earlier policy's
"within 250 m of observed flooding" verification is not part of the fused
ladder (documented side effect in the M1C.3 report).
