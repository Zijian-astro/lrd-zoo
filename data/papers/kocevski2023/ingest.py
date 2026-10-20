"""Build objects.csv for Kocevski et al. 2023 ("Hidden Little Monsters": two broad-line AGN at z>5 in CEERS).

Raw file: arXiv LaTeX source of 2302.00012 (https://arxiv.org/e-print/2302.00012, v1), saved as
  arxiv_2302.00012.tar.gz   (member main.tex is read directly from the tarball)

Table used: tab_sample "AGN Sample" (2 rows, RA/Dec in decimal degrees, z, m_F356W).
X-ray: the text states neither source is detected in the 800 ks AEGIS-XD Chandra data -> xray=nondet.

Usage: python ingest.py <dir containing arxiv_2302.00012.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2302.00012.tar.gz") as tf:
    tex = tf.extractfile("main.tex").read().decode("utf-8")
assert "Neither source is directly detected in the deep (800 ksec) Chandra X-ray observations" in tex

i = tex.index(r"\label{tab_sample}")
beg = tex.rindex(r"\begin{tabular}", 0, i)
body = tex[beg:tex.index(r"\end{tabular}", beg)]
data = body.split(r"\hline")[3]            # [1],[2] = \hline\hline around header, [3] = data rows

rows = []
for line in data.split(r"\\"):
    line = re.sub(r"(?m)%.*$", "", line).strip()
    if not line:
        continue
    cells = [c.strip() for c in line.split("&")]
    m = re.fullmatch(r"CEERS~(\d+)", cells[0])
    assert m, cells
    float(cells[1]), float(cells[2]), float(cells[3])
    rows.append((f"CEERS-{m.group(1)}", cells[1], cells[2], cells[3]))
assert len(rows) == 2

notes = {"CEERS-1670": "same source as the AGN candidate of Onoue+2023 (table note)",
         "CEERS-3210": "inferred to be a heavily obscured broad-line AGN"}
out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "notes"])
    for oid, ra, dec, z in rows:
        w.writerow([oid, ra, dec, z, "spec", "EGS", "", "NIRSpec/grating", "1", "nondet", notes[oid]])
print(f"wrote {out} ({len(rows)} rows)")
