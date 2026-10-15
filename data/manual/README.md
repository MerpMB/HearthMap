# data/manual/ - manually supplied sources

Some official sources cannot be fetched by the agent environment (the Ministry of Education catalogue refuses
connections from it; MoPH HCODE sits behind a browser/bot challenge that must not be bypassed). They **exist** and are
**lawfully obtainable by the project user**. Put the file here and the importer gives it the same provenance as an
automated download.

```
data/manual/<source_id>/<original file name>      # untouched original (.xlsx / .csv)
data/manual/<source_id>/MANIFEST.yaml             # copy of MANIFEST.template.yaml, filled in
```

`<source_id>` is one of `moe-register-current` or `moph-hcode-export` (see `config/manual-imports.yaml`).

Rules
* The directory contents are **ignored by Git** (raw datasets may carry licences that forbid redistribution); only this README and
  `MANIFEST.template.yaml` are tracked.
* Never edit the original. The importer recomputes its SHA-256 and refuses a mismatch.
* Never put credentials, cookies or tokens in the manifest or the file name.
* Do not bypass a bot challenge or a login to obtain a file; download it in a normal browser session you are entitled to.
* Import: `python scripts/m2a2/import_manual.py <source_id>` validates the schema, ids, coordinates, provinces, internal dates and
  coverage, writes a report to `outputs/m2a2-review/`, and only then copies the file to `data/raw/<source_id>/manual-<date>/`.
