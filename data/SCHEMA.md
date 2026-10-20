# Data format

Every paper is one folder: `data/papers/<key>/`, where `<key>` is the first author's
surname in lowercase ASCII plus the year (`kocevski2025`, `zhang2025b` if needed).

```
data/papers/<key>/
  meta.yaml     bibliographic + provenance metadata
  objects.csv   one row per object, exactly as listed in that paper
  ingest.py     (optional) script that rebuilds objects.csv from the raw download
```

Run `python scripts/validate.py <key>` after editing, then `python scripts/build_catalog.py`.

## meta.yaml

| key | required | meaning |
|---|---|---|
| `key` | yes | same as the folder name |
| `first_author` | yes | surname, e.g. `Kocevski` |
| `label` | no | short citation label shown on the site; default `Firstauthor+YY` |
| `authors` | no | `"Surname, I., Surname, I., et al."` |
| `year` | yes | publication year (arXiv year if unpublished) |
| `title` | yes | paper title |
| `journal` | no | `"ApJ, 986, 126"`; leave out if not yet published |
| `arxiv` | one of arxiv/doi | `2404.03576` (no `arXiv:` prefix, no version) |
| `doi` | one of arxiv/doi | journal DOI |
| `ads_bibcode` | no | `2025ApJ...986..126K` |
| `selection` | yes | how the sample was built: `photometric`, `spectroscopic`, `grism`, `variability`, `xray`, `radio`, `infrared`, `compilation`, `individual`, `local` |
| `sample_is_lrd` | no (default `true`) | `true` if the paper calls every object an LRD; `false` if the sample is broader (e.g. all broad-line AGN) and only rows with `lrd=1` are LRDs |
| `facility` | no (default `JWST`) | where the objects were found: `JWST`, `Euclid`, `HST`, `SDSS`, `ground`; the site can hide non-JWST candidates |
| `tags` | no | data the paper provides: `nirspec`, `grism`, `photometry`, `xray`, `variability`, `miri`, `alma`, `radio`, `ground-spec` |
| `fields` | no | survey fields covered |
| `n_objects` | yes | number of rows the paper's table has (the validator warns if objects.csv differs) |
| `source_url` | yes | where the table came from (VizieR, Zenodo, journal MRT, arXiv source, GitHub) |
| `source_note` | yes | which table, and any cuts or conversions you made |
| `notes` | no | anything a user should know (e.g. "positions from the CEERS DR0.5 mosaic") |

## objects.csv

Required columns: `id, ra, dec`. Optional columns (leave a cell empty when unknown):

| column | values | meaning |
|---|---|---|
| `id` | text | the identifier used in the paper (prefix with the survey if the paper only gives a number, e.g. `CEERS-7902`) |
| `ra`, `dec` | decimal degrees, J2000 | as published; convert sexagesimal with astropy, keep ≥6 decimals |
| `z` | number | the paper's adopted redshift |
| `z_type` | `spec`, `grism`, `phot` | where `z` comes from |
| `field` | text | survey field as the paper names it |
| `lrd` | `1`, `0`, empty | `1` = the paper classifies it as an LRD, `0` = in the sample but explicitly not an LRD |
| `spec` | `NIRSpec/PRISM`, `NIRSpec/grating`, `NIRSpec`, `NIRCam/grism`, `NIRISS/grism`, `ground`, empty | spectrum used in this paper |
| `broad_line` | `1`, `0`, empty | broad Balmer (or Paschen) line detected in this paper |
| `xray` | `det`, `nondet`, empty | X-ray result in this paper |
| `variable` | `1`, `0`, empty | variability result in this paper (`0` = tested, not variable) |
| `f444w` | AB mag | if given |
| `notes` | text | short free text |

Never type coordinates by hand from a PDF figure; always take them from a table.

## Corrections

If a published table has a clear error (for example two objects with swapped positions), leave
`objects.csv` as published and add a fix to `data/corrections.yaml` with the reason and the source of
the corrected value. The build applies it and the web page marks the entry as corrected.
