"""Build objects.csv for Tee et al. 2025 (ApJL 983, L26; arXiv:2412.05242),
"Lack of Rest-frame UV Variability in Little Red Dots Based on HST and JWST Observations".

Raw file: arxiv_2412.05242.src (arXiv LaTeX source, tar.gz, v1 = submitted version)
  Table 2 (tab:variability_result): 21 LRDs with sexagesimal RA/Dec, z_best, HST-JWST magnitude
  changes. The paper finds no source with >3 sigma variability (variable=0 for all).
Field is taken from the ID prefix following paper Table 1 (EGS = CEERS, GOODS-S = JADES,
Abell 2744 = UNCOVER).

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2412.05242.src") as tf:
    tex = tf.extractfile("var_agn_LRD.tex").read().decode("utf-8")
assert "none show $>3\\sigma$ variability" in tex

seg = tex[tex.index(r"\label{tab:variability_result}"):]
seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
seg = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in seg.splitlines())
FIELD = {"JADES": "GOODS-S", "CEERS": "EGS", "UNCOVER": "Abell 2744"}

rows = []
for row in seg.split(r"\\"):
    row = row.strip()
    if not row:
        continue
    c = [x.strip() for x in row.split("&")]
    assert len(c) == 11, c
    name = c[0].replace(r"\_", "_")
    coord = SkyCoord(c[1], c[2], unit=(u.hourangle, u.deg))
    dm125 = c[7].replace(r"$\pm$", "+/-")
    dm160 = c[8].replace(r"$\pm$", "+/-")
    notes = [f"dm(F125W)={dm125} mag", f"dm(F160W)={dm160} mag"]
    assert c[9] in ("Y", "N"), c[9]
    if c[10]:
        cite = re.fullmatch(r"\\cite\{([^}]+)\}", c[10]).group(1)  # e.g. Harikane2023ApJ...959...39H
        notes.append(f"Table 2 'BL detected'={c[9]} (BL/MBH ref {cite})")
    elif c[9] == "Y":
        notes.append("Table 2 'BL detected'=Y")
    rows.append([name, f"{coord.ra.deg:.7f}", f"{coord.dec.deg:.7f}", c[3], "", FIELD[name.split("_")[0]],
                 "1", "0", "; ".join(" ".join(n.split()) for n in notes)])
assert len(rows) == 21, len(rows)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "variable", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
