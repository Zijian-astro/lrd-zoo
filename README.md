# LRD Zoo

A living compilation of every published JWST "little red dot" (LRD), cross-matched across
papers, with a web page that answers one question fast: **has this source already been published?**

- **Position search**: paste RA/Dec (decimal, sexagesimal or J-names, one per line) or upload a
  CSV; every published object within the match radius comes back with the papers that reported it.
- **Catalogue**: one row per unique object, merged from all papers, with filters (field, redshift,
  spectrum, broad line, X-ray, variability, MIRI, JWST vs wide-field) and CSV export.
- **Object pages**: every paper's ID, redshift and classification for the object, a DJA NIRCam
  cutout, links to SIMBAD/VizieR/ESASky, and one-click BibTeX for exactly the papers involved.
- **Charts**: sky positions per field, redshift distribution, growth of the population over time.
- **New on arXiv**: a daily check for new LRD papers on arXiv (and VizieR, and optionally ADS full
  text); each new one opens a GitHub issue so it does not get forgotten, and papers whose tables are
  on VizieR are marked.

Everything is static (HTML + JS + JSON), so it runs on GitHub Pages with no server.

## Layout

```
index.html, assets/          the web page
data/papers/<key>/           one folder per paper: meta.yaml, objects.csv, ingest.py
data/SCHEMA.md               the format of those folders
data/corrections.yaml        fixes for clear errors in published tables (applied at build time)
data/candidates.md           sample papers found but not added yet, and why
data/zoo_ids.json            registry of permanent Zoo names (commit this)
data/arxiv_inbox.json        output of the arXiv monitor (commit this)
data/arxiv_ignore.yaml       arXiv IDs to mark as "ignored" (theory papers, no object table)
data/build/                  generated catalogue (not committed; built by CI)
scripts/validate.py          checks every paper folder
scripts/build_catalog.py     merges papers -> data/build/
scripts/arxiv_monitor.py     updates data/arxiv_inbox.json (arXiv, VizieR, optional ADS)
.github/workflows/site.yml   daily arXiv check + build + deploy to GitHub Pages
docs/ingest-routine.md       instructions for the weekly ingestion routine (Claude Code, opens PRs)
```

## Run it locally

```bash
pip install -r requirements.txt
python scripts/validate.py
python scripts/build_catalog.py
python -m http.server 8000      # then open http://localhost:8000
```

## Add a paper

1. Create `data/papers/<firstauthor><year>/` (e.g. `smith2026`).
2. Write `meta.yaml` (title, authors, arXiv ID, how the sample was selected, where the table came from).
3. Write `objects.csv` with at least `id,ra,dec`, plus `z,z_type,lrd,spec,broad_line,xray,variable` when the paper gives them.
   Take the values from a machine-readable table (VizieR, Zenodo, the journal's MRT, or the arXiv
   LaTeX source). If you convert a table with a script, save it as `ingest.py` in the same folder.
4. `python scripts/validate.py <key>` and `python scripts/build_catalog.py`. The build prints
   objects whose positions from different papers disagree, which is worth a look.
5. Commit and push. The workflow rebuilds and redeploys the site.

The full field list is in [data/SCHEMA.md](data/SCHEMA.md). Papers without coordinates cannot be
added; put their arXiv ID in `data/arxiv_ignore.yaml` with a short reason so they stop showing as "to review".

## Corrections

Published tables sometimes contain slips (swapped positions, a wrong digit). `objects.csv` always
stays exactly as published; fixes go in `data/corrections.yaml` with the reason and the independent
source of the corrected value, and the web page marks those entries as corrected. The current fixes
cover position mix-ups in Yue+24 and Perger+25, a Dec typo in Lin+26, and a Dec slip in Zhang+25.

## How objects are merged

Rows from different papers within 0.5″ (`--radius`) are grouped friends-of-friends into one object.
The object's position is the mean of the papers' positions. Its name, `LRDZ Jhhmmss.ss±ddmmss.s`,
is minted from its position the first time it appears and stored in `data/zoo_ids.json`, so names
stay fixed when later papers move the mean position slightly.

An object counts as an LRD if at least one paper calls it one. Papers that list broad-line AGN in
general set `sample_is_lrd: false` and flag their LRDs row by row. The adopted redshift is the most
recent spectroscopic one, then grism, then photometric.

## Deploy on GitHub Pages

1. Create a repository (e.g. `lrd-zoo`) and push this folder to `main`.
2. In the repository, open Settings → Pages and set Source to **GitHub Actions**.
3. Set `repoUrl` at the top of `assets/app.js` to the repository URL, so the page links to it.
4. Optional: run the workflow once by hand (Actions → Build and deploy → Run workflow).

The workflow runs on every push and once a day; see [Keeping up with new papers](#keeping-up-with-new-papers).

## Keeping up with new papers

Finding new papers is automatic; adding a paper's table goes through a pull request that a person
reviews. Nothing reaches `main` without the maintainer merging it.

| when | what | where |
|---|---|---|
| daily, 05:23 UTC | `arxiv_monitor.py --days 7 --open-issues`: arXiv search, VizieR check, ADS full-text search (if the token is set); commits `data/arxiv_inbox.json`, opens/labels issues, rebuilds the site | `.github/workflows/site.yml` |
| weekly, Monday 07:00 UTC | a Claude Code cloud routine ingests up to 5 `has-sample` issues and opens one PR per paper | [docs/ingest-routine.md](docs/ingest-routine.md) |
| on merge | validate, build, register new Zoo names, redeploy | `.github/workflows/site.yml` |

**Sources the monitor checks**

- **arXiv**: title or abstract mentions "little red dot(s)" or "LRDs" (astro-ph.GA/CO/HE/SR).
- **VizieR** (no account needed): a keyword search for LRD catalogues, plus a lookup of every
  published inbox paper by the VizieR name implied by its journal reference (`A&A 702, A57` ->
  `J/A+A/702/A57`) or ADS bibcode. A paper with a table there gets `"vizier": [...]` in the inbox and
  a "VizieR table" link on the New on arXiv tab. The top-level `"vizier"` key lists every catalogue
  found, with the day it was first seen; an LRD catalogue that matches no paper gets its own issue.
- **ADS full text** (optional): set a repository secret `ADS_API_TOKEN` (Settings -> Secrets and
  variables -> Actions; a token from https://ui.adsabs.harvard.edu/user/settings/token). The monitor
  then also finds papers that mention little red dots only in the body (`"fulltext_only": true`,
  shown under "Body mentions", no issue opened for them unless they have a VizieR table) and records
  every inbox paper's journal bibcode and DOI, which makes the VizieR lookup exact. Without the
  secret everything else works as before.

**Issues** (label `new-paper`): one per new arXiv paper. `has-sample` is added when the abstract
mentions a sample or the paper has a VizieR table; `vizier` when it has a VizieR table (an open issue
that gains a table gets both labels and a comment). At most 10 new issues per run; the rest follow
on the next runs.

**Weekly routine**: reads open `has-sample` issues, downloads each paper's table (VizieR, journal
machine-readable table, Zenodo/GitHub, or the arXiv LaTeX source), writes `data/papers/<key>/` with
an `ingest.py`, runs `validate.py` and `build_catalog.py`, and opens a PR per paper (branch
`claude/ingest-<key>`) with a checklist of what it checked and what to look at. Papers that are
clearly not sample papers get a one-line PR adding them to `data/arxiv_ignore.yaml`. It never pushes
to `main` or merges. Its prompt and setup (GitHub access, network allowlist) are in
[docs/ingest-routine.md](docs/ingest-routine.md). To queue a paper by hand, open an issue titled
`[arXiv <id>] <title>` with labels `new-paper` and `has-sample`; add `ingest-skip` to keep the routine
away from an issue, `ingest-retry` to let it try again after a rejected PR.

**Still needs a person**: reviewing and merging each PR (checking the selection, `sample_is_lrd` and
the flags against the paper), deciding on corrections to published tables (`data/corrections.yaml`),
papers without public coordinates (`data/candidates.md`), and closing issues of papers that are not
worth adding (or merging the routine's ignore PRs).

## Credit

The object data belong to the authors of the papers listed on the site; please cite them. Each
paper's `meta.yaml` records exactly where its table came from.
