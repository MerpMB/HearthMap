# GISTDA flood products — what the publisher documents (M1C.2)

Checked 2026-10-15. Sources inspected: the ArcGIS layer, service and portal item
JSON of the legacy product; the GISTDA open-data catalogue (CKAN `package_show`
for `disasters-01` and `flood-disaster-data`, `package_search` for flood
datasets); the GISTDA API Postman collection (folder "Flood recurrence");
`https://disaster.gistda.or.th/landing/services` (a JavaScript application whose
static HTML contains no methodology text). Nothing below is inferred.

Roles during M1C.2: 2011–2023 = `PRIMARY_CURRENT_PRODUCT`, 2005–2016 =
`LEGACY_COMPARISON_PRODUCT`. Neither role means "correct" or "wrong".

| Topic | 2005–2016 (`FL_RepeatedFlooding_GISTDA_50k_Y2005_Y2016`) | 2011–2023 (`disasters-01`, API `flood-recurrence`) |
|---|---|---|
| Title / description | "พื้นที่น้ำท่วมซ้ำซาก ปี 2005 -2016" (repeated flooding areas 2005–2016); layer `description` empty | "ชั้นข้อมูลพื้นที่น้ำท่วมซ้ำซากในรอบ 13 ปี (2011-2023)" (13-year cycle); Postman: "Flood recurrence based on the frequency of floods in 10-year period. The methodological approach focuses on areas that have actually been affected by floods." |
| Input imagery | **Not documented** | **Not documented** |
| Classification methodology | **Not documented** | Only the sentence above ("areas that have actually been affected by floods") |
| Spatial resolution / scale | "50k" in the layer name only (1:50,000 implied by name) | "Spatial: 20 m." (Postman metadata table) |
| Cloud handling | **Not documented** | **Not documented** |
| Minimum mapping unit | **Not documented** | **Not documented** |
| Water masking (permanent water) | **Not documented** | **Not documented** |
| Annual composite method | **Not documented**; yearly 0/1 fields `year2005`…`year2016` | **Not documented**; yearly `detail[].freq` described as "ความถี่ที่พบในแต่ละปี" (frequency found in each year); all values are 0/1 |
| Post-processing / generalisation | **Not documented** | **Not documented**; polygons arrive clipped to the query area and split by sub-district |
| Recurrence field | `flood_freq` (no description); equals Σ yearly flags for every AOI feature | `total` = "ผลรวมของจำนวนครั้งที่เกิดน้ำท่วมซ้ำซาก" (sum of the number of recurring floods); equals Σ yearly freq for every feature |
| Quality statement | none | "Quality: -" (Postman) |
| Update | Portal item created 2017-12-21, modified 2021-11-29 | Catalogue `update_frequency_unit` "ไม่ทราบ" (unknown) vs Postman "Update: Yearly"; catalogue created 2025-05-26, metadata modified 2026-09-04 |
| Licence | Portal `licenseInfo`: none; service copyright "GISTDA" | "Open Data Common" (catalogue) |
| Coverage | Thailand (service extent) | "Thailand" |

## Metadata inconsistencies (recorded, not resolved)

1. **13 years vs "10-year period".** The catalogue says the layer covers 13 years
   (2011–2023) and every feature carries 13 yearly values; the Postman
   description says recurrence is based on "the frequency of floods in 10-year
   period". Which applies to `total` is not stated. The data itself sums 13
   yearly values.
2. **Update frequency:** "unknown" (catalogue) vs "Yearly" (Postman).
3. **Catalogue example URL** points at API `v1.0`; the Postman collection and
   HearthMap use `v1.1`.

## Observations from the legacy service schema (field names only)

The legacy layer carries fields named `fid_flood2005_2016_utm`,
`fid_fl2005_11`, `fid_polbndry_2554_geo_send03` and
`gisdata.ugisdata.flood2005_2016_geoadm.area`. Their names suggest the product
was assembled from earlier parts and intersected with a 2554 (2011)
administrative boundary layer, but **no documentation confirms this**, and
HearthMap does not rely on it.

## Conclusion

Neither product documents its imagery, classification, cloud handling, minimum
mapping unit, water masking, compositing or generalisation. Methodology is
**unavailable**; differences between the products cannot be attributed to a
documented processing step.
