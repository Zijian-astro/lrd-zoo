"""Build objects.csv for Lin et al. 2024 (ASPIRE: broad-line AGN at z=4-5 revealed by JWST/NIRCam WFSS).

Raw file: arXiv LaTeX source of 2407.17570 (https://arxiv.org/e-print/2407.17570, v1, "Accepted by the ApJ"), saved as
  arxiv_2407.17570.tar.gz   (member tab1.tex is read directly from the tarball)

Table used: tab:basic (tab1.tex) "The coordinate, redshift, and AB magnitude in F356W of the 16 LRDs in the ASPIRE
fields" -- RA/Dec in decimal degrees with 4 decimals (written as published), grism Halpha redshift.
Field = the ASPIRE quasar field encoded in the ID (J0109M3047 -> J0109-3047, P -> +).

Usage: python ingest.py <dir containing arxiv_2407.17570.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2407.17570.tar.gz") as tf:
    tex = tf.extractfile("tab1.tex").read().decode("utf-8")
assert r"\label{tab:basic}" in tex and "16 LRDs" in tex

body = tex[tex.index(r"\begin{tabular}"):tex.index(r"\end{tabular}")].split(r"\hline")[2]
rows = []
for line in body.split(r"\\"):
    line = line.strip()
    if not line:
        continue
    cells = [c.strip() for c in line.split("&")]
    oid = cells[0]
    m = re.fullmatch(r"J(\d{4})([MP])(\d{4})-BHAE-\d", oid)
    assert m, oid
    field = f"J{m.group(1)}{'-' if m.group(2) == 'M' else '+'}{m.group(3)}"
    ra, dec = cells[1].strip("$ "), cells[2].strip("$ ")
    z = cells[3].split("$")[0]
    float(ra), float(dec), float(z)
    rows.append((oid, ra, dec, z, field))
assert len(rows) == 16

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line"])
    for oid, ra, dec, z, field in rows:
        w.writerow([oid, ra, dec, z, "grism", field, "1", "NIRCam/grism", "1"])
print(f"wrote {out} ({len(rows)} rows)")
