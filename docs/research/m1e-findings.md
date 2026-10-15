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

**Verification burden.** 86.1% of the AOI calls for site verification for at least one
family (0 families 19.1%, 1: 44.3%, 2: 30.4%, 3: 6.2%). The burden is broad, so it
discriminates little on its own; its value is in naming *which* information is needed.

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
