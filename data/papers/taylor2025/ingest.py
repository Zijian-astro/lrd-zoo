"""Build objects.csv for Taylor et al. 2025 (CEERS+RUBIES broad-line AGN at 3.5<z<6, BH mass function, LRD connection).

Raw file: arXiv LaTeX source of 2409.06772 (https://arxiv.org/e-print/2409.06772, v2 = accepted version), saved as
  arxiv_2409.06772.tar.gz   (member main.tex is read directly from the tarball)

Table used: tab:sample "Sample of BLAGN" -- 63 spectra of 62 objects (RUBIES-EGS-50052 and CEERS-2782 are the same
source observed by both surveys; both rows kept, as in the paper). RA/Dec already in decimal degrees.
Per the table comment: dagger = LRD (Kocevski+24 criteria) -> lrd=1, all other rows lrd=0;
double dagger = fit with an absorption feature.

Usage: python ingest.py <dir containing arxiv_2409.06772.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2409.06772.tar.gz") as tf:
    tex = tf.extractfile("main.tex").read().decode("utf-8")

i = tex.index(r"\label{tab:sample}")
start = tex.index(r"\startdata", i) + len(r"\startdata")
body = tex[start:tex.index(r"\enddata", start)]

DAG = r"\textsuperscript{\textdagger}"
DDAG = r"\textsuperscript{\textdaggerdbl}"
rows = []
for line in body.split(r"\\"):
    line = re.sub(r"(?m)%.*$", "", line).strip()
    if not line:
        continue
    cells = [c.strip() for c in line.split("&")]
    assert len(cells) == 9, cells
    idcell = cells[0]
    lrd = DAG in idcell
    absorb = DDAG in idcell
    oid = idcell.replace(DAG, "").replace(DDAG, "").strip()
    assert re.fullmatch(r"(RUBIES-(EGS|UDS)|CEERS)-\d+", oid), oid
    ra, dec, z = cells[1], cells[2], cells[3]
    float(ra), float(dec), float(z)
    rows.append((oid, ra, dec, z, lrd, absorb))

assert len(rows) == 63 and len({r[0] for r in rows}) == 63
n_lrd = sum(r[4] for r in rows)
same = {"RUBIES-EGS-50052": "same object as CEERS-2782 (observed by both RUBIES and CEERS)",
        "CEERS-2782": "same object as RUBIES-EGS-50052 (observed by both RUBIES and CEERS)"}

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    for oid, ra, dec, z, lrd, absorb in rows:
        field = "UDS" if oid.startswith("RUBIES-UDS") else "EGS"
        notes = []
        if absorb:
            notes.append("broad Halpha fit with an absorption feature")
        if oid in same:
            notes.append(same[oid])
        w.writerow([oid, ra, dec, z, "spec", field, "1" if lrd else "0", "NIRSpec/grating", "1", "; ".join(notes)])
print(f"wrote {out} ({len(rows)} rows, {n_lrd} lrd=1)")
