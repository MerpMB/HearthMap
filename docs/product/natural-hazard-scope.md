# Natural Hazard Resilience — scope and completeness (after M1D)

Status: **regional evidence implemented for hydrogeomorphic and seismic hazards; the
dimension is NOT complete.** It must not receive a suitability score, and nothing here is a
parcel- or site-level safety statement. `hazard_resilience` (25% provisional weight in
`config/scoring.yaml`) is not ready for scoring.

## Regional evidence implemented (provisional)

| Family | Evidence | Source |
|---|---|---|
| **Hydrogeomorphic — flood** | source-aware 2005–2023 observation ledger and flood ladder; selected provisional policy `FLOOD_ANY_SOURCE` | GISTDA 2011–2023 (primary) + 2005–2016 (legacy corroboration) |
| **Hydrogeomorphic — landslide susceptibility** | DMR susceptibility classes, inventory scars (corroborating) | DMR |
| **Hydrogeomorphic — terrain proxy** | DSM slope statistics (never deprioritizes alone) | Copernicus GLO-30 DSM |
| **Seismic — active-fault context** | distance, nearest group, trace counts (descriptive, no score) | DMR active-fault traces |
| **Seismic — probabilistic earthquake hazard / intensity context** | PGA hazard (10% in 50 years, Sadigh et al. 1997) shown as MMI zones | DMR `EQ_ZONE` |
| **Seismic — historical seismicity** | per-source event metrics (corroborating, never reassuring) | DMR inventory, TMD felt events, USGS ComCat |

Selected provisional defaults for regional screening (`config/regional-screening-defaults.yaml`):
hydrogeomorphic profile `BALANCED`, flood policy `FLOOD_ANY_SOURCE`
(`selected_for_provisional_screening: true`, `production_truth: false`; remaining
M1C–M1C.3 visual QA pending). They are a project risk-tolerance decision, not a scientific
optimum. No seismic policy is selected; the seismic interpretation is experimental.
Hydrogeomorphic and seismic results are independent and are only cross-tabulated.

## Integration (M1E)

Hazard-family outcomes are translated into separate decision axes (regional search action,
site verification, engineering mitigation, data completeness) by
[natural-hazard-integration.md](natural-hazard-integration.md); there is no scalar hazard
score. Regional seismic shaking requires engineering mitigation and site verification; it does
not deprioritize a region. The future suitability contract is designed but not activated.

## Site-level evidence still missing

* local geology and ground material; sediment thickness and basin effects
* site amplification and Vs30
* liquefaction susceptibility
* building design / code zone and site engineering
* parcel-specific geotechnical and seismic investigation

Regional seismic screening does not replace any of this. Missing ground-response evidence
limits claims (no parcel-level seismic safety) but does not make regional screening unusable.

## Other hazards not yet covered (backlog)

| Hazard | Status | Registry |
|---|---|---|
| Wildfire / seasonal burning | Not covered (fire hotspots only as a livability candidate) | `fire-hotspots-firms` (CANDIDATE) |
| Modelled debris flow / flash flood | Not covered | `debris-flow-flash-flood-dmr` (CANDIDATE) |
| Flooding after 2023 / current events | Not covered (record ends 2023) | `flood-gistda-event` (CANDIDATE) |
| Sinkholes, karst, other geological hazards | Not covered (DMR sinkhole services exist) | — |
| Future climate effects | Not covered | — |

## Rules

1. Until site-level seismic evidence exists, no document or UI may describe a location as
   earthquake-safe or the Natural Hazard dimension as complete.
2. Distance to a fault trace is context, not risk; there is no fault distance score.
3. Any document or UI showing screening outputs must carry the scope statement
   "Regional hazard screening only (hydrogeomorphic: observed flood, landslide
   susceptibility, DSM terrain; seismic: active-fault context, probabilistic hazard zones,
   historical events); not a site-level or complete natural-hazard assessment."
