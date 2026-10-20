"""Build objects.csv for Setton et al. 2025 (Little Red Dots at an inflection point: V-shaped turnover at the Balmer limit).

Raw file: arXiv LaTeX source of 2411.03424 (https://arxiv.org/e-print/2411.03424, v1 -- the only arXiv version), saved as
  arxiv_2411.03424.tar.gz   (member LRD_Breaks.tex is read directly from the tarball)

Table used: tab:LRD_sample -- "all extremely red (B-R>0.95) Halpha emitters (rest-frame EW>400 A) from the RUBIES survey
or public PRISM data", 44 rows (Program, ID, RA, Dec [decimal deg, 4 decimals], z, m_F444W, ..., Delta k with errors).

LRD flag: the paper calls the sources whose change in slope k_red-k_blue (Delta k) is >0 at the 2 sigma level
"V-shaped Little Red Dots" (20/44 per the abstract). The table gives Delta k with 16th/84th-percentile errors; we set
lrd=1 where Delta k - 2*sigma_lower > 0, which reproduces exactly 20 (asserted). Other rows: lrd empty (the paper does
not say they are not LRDs).
IDs follow the paper's text convention <Program>-<ID> (e.g. RUBIES-uds-40579, UNCOVER-45924, 6585-58018).
field: from the RUBIES ID (uds/egs), otherwise from the position for the standard deep fields; empty if none applies.

Usage: python ingest.py <dir containing arxiv_2411.03424.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2411.03424.tar.gz") as tf:
    tex = tf.extractfile("LRD_Breaks.tex").read().decode("utf-8")

i = tex.index(r"\label{tab:LRD_sample}")
beg = tex.rindex(r"\begin{tabular}", 0, i)
body = tex[beg:tex.index(r"\end{tabular}", beg)].split(r"\hline")[1]   # between the two \hline = data rows

FIELDS = [  # (name, ra_min, ra_max, dec_min, dec_max) -- broad boxes around the standard deep fields
    ("GOODS-S", 52.8, 53.4, -28.1, -27.5), ("GOODS-N", 188.8, 189.7, 62.0, 62.5),
    ("Abell 2744", 3.3, 3.9, -30.6, -30.1), ("COSMOS", 149.3, 150.9, 1.5, 3.0),
    ("EGS", 214.4, 215.5, 52.5, 53.3), ("UDS", 34.0, 34.9, -5.5, -4.8)]
PM = re.compile(r"([-0-9.]+)\s*\$\\pm\s*\^\{([0-9.]+)\}_\{([0-9.]+)\}\$")

rows = []
for line in body.split(r"\\"):
    line = line.strip()
    if not line:
        continue
    cells = [c.strip() for c in line.split("&")]
    assert len(cells) == 11, cells
    prog, sid, ra, dec, z, f444w = cells[:6]
    float(ra), float(dec), float(z), float(f444w)
    dk, dk_up, dk_lo = (float(x) for x in PM.fullmatch(cells[10]).groups())
    lrd = dk - 2 * dk_lo > 0
    if prog == "RUBIES":
        fld, rest = sid.split("-")
        field = {"uds": "UDS", "egs": "EGS"}[fld]
    else:
        field = next((n for n, r0, r1, d0, d1 in FIELDS
                      if r0 < float(ra) < r1 and d0 < float(dec) < d1), "")
    rows.append(dict(id=f"{prog}-{sid}", ra=ra, dec=dec, z=z, field=field, lrd=lrd, f444w=f444w, prog=prog,
                     dk=cells[10]))

assert len(rows) == 44 and len({r["id"] for r in rows}) == 44, len(rows)
n_lrd = sum(r["lrd"] for r in rows)
assert n_lrd == 20, n_lrd           # abstract: "a large fraction (20/44 ...) ... exhibit a strong change in slope"

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w", "notes"])
    for r in rows:
        notes = []
        if r["lrd"]:
            notes.append("V-shaped: Delta k>0 at 2 sigma")
        if r["prog"] == "JADES":
            notes.append("JADES spectroscopic ID")
        if not r["prog"].isalpha():
            notes.append(f"JWST program {r['prog']}")
        w.writerow([r["id"], r["ra"], r["dec"], r["z"], "spec", r["field"], "1" if r["lrd"] else "",
                    "NIRSpec/PRISM", "", r["f444w"], "; ".join(notes)])
print(f"wrote {out} ({len(rows)} rows, {n_lrd} lrd=1, {sum(not r['field'] for r in rows)} without field)")
