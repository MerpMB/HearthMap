# Natural Hazard Resilience — scope and completeness

Status: **INCOMPLETE.** The *Natural Hazard Resilience* dimension
(`hazard_resilience`, 25% provisional weight in `config/scoring.yaml`) is **not**
ready for suitability scoring.

## Implemented (v0.1)

| Scope | Implemented as | Sources |
|---|---|---|
| **HYDROGEOMORPHIC** | *Hydrogeomorphic Hazard Screening v0.1* — evidence (M1B) and provisional regional screening policy (M1C) | observed flooding 2005–2016 (GISTDA, temporary evidence), DMR landslide susceptibility + inventory, Copernicus GLO-30 DSM terrain |

M1C is a **regional screening** of hydrogeomorphic concerns only. It must never
be described — in documentation, maps or a future UI — as complete
natural-hazard safety, and its outcomes never mean "safe", "buildable" or
"rejected".

## Not yet covered (explicit backlog)

| Hazard | Status | Next step | Registry |
|---|---|---|---|
| Seismic — active faults | **Required** before Natural Hazard Resilience can be considered complete enough for scoring | Acquire DMR active fault traces (640 segments, 14 zones incl. Mae Chan, Mae Ing, Mae Tha, Phayao); define a documented seismic methodology | `seismic-active-faults-dmr` (CANDIDATE, metadata verified) |
| Earthquake hazard (ground shaking) | Not covered | Evaluate DMR intensity zones and building-code seismic zones; never use simple distance-to-fault as an earthquake-risk score | `seismic-intensity-zones-dmr` (CANDIDATE) |
| Wildfire / seasonal burning | Not covered (fire hotspots exist only as a livability candidate) | Define whether wildfire exposure is a hazard or livability concern | `fire-hotspots-firms` (CANDIDATE) |
| Modelled debris flow / flash flood | Not covered | AOI subset of DMR modelled impact areas | `debris-flow-flash-flood-dmr` (CANDIDATE) |
| Current flood recurrence (2011–2023) | Blocked | Project API key from GISTDA | `flood-gistda-history` (BLOCKED_CREDENTIAL_REQUIRED) |
| Sinkholes, other geological hazards | Not covered | Research DMR sinkhole services (H_SINKHOLE) | — |
| Climate-change projections | Not covered | Later | — |

## Rules

1. Until seismic hazard is implemented with a documented methodology,
   `hazard_resilience` cannot receive a suitability score.
2. Distance to a fault trace is context, not risk.
3. Any document or UI that shows M1C outputs must carry the scope statement
   "Hydrogeomorphic screening only (flood observed 2005–2016, landslide
   susceptibility, DSM terrain); not a complete natural-hazard assessment."
