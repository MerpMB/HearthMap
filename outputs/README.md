# outputs/

Generated artifacts (grids, scored layers, QGIS exports, reports). **Untracked.**
Every artifact must be reproducible from code + `data/raw/` and must have a
`.provenance.json` sidecar. Anything produced from synthetic input carries
`"synthetic": true` in its provenance.
