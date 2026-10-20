"""Build objects.csv for Harikane et al. 2023 (JWST/NIRSpec first census of broad-line AGNs at z=4-7).

Raw file: arXiv LaTeX source of 2303.11946 (https://arxiv.org/e-print/2303.11946, v3 = accepted version), saved as
  arxiv_2303.11946.tar.gz   (member ms_jwst_blagn_v1.tex is read directly from the tarball)

Table used: tab_N23 "Physical Properties of Our Faint Type-1 AGNs" -- two blocks:
  "Our Final Broad-Line AGN Sample" (10 objects)  -> broad_line=1
  "Other Possible Candidates with SNR_broad<5" (2) -> broad_line empty, noted as candidates
Sexagesimal J2000 RA/Dec -> degrees with astropy SkyCoord.

Usage: python ingest.py <dir containing arxiv_2303.11946.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2303.11946.tar.gz") as tf:
    tex = tf.extractfile("ms_jwst_blagn_v1.tex").read().decode("utf-8")

i = tex.index(r"\label{tab_N23}")
start = tex.index(r"\startdata", i) + len(r"\startdata")
body = tex[start:tex.index(r"\enddata", start)]

# notes from the table comments (Kocevski+2023 names; CEERS_01019 is Larson+2023's CEERS_1019)
alias = {"CEERS_00746": "CEERS 3210 in Kocevski+2023", "CEERS_02782": "CEERS 1670 in Kocevski+2023",
         "CEERS_01019": "CEERS_1019 of Larson+2023; broad SNR is for Hbeta"}

rows, block = [], None
for line in body.split(r"\\"):
    line = re.sub(r"(?m)%.*$", "", line).replace(r"\hline", "").strip()
    if not line:
        continue
    if line.startswith(r"\multicolumn"):
        block = "final" if "Final Broad-Line AGN Sample" in line else "candidate"
        assert block == "final" or "Other Possible Candidates" in line, line
        continue
    cells = [c.strip() for c in line.split("&")]
    name = re.sub(r"\$\^.*?\$", "", cells[0]).replace(r"\_", "_").strip()
    assert re.fullmatch(r"(CEERS|GLASS)_\d+", name), name
    ra_s = cells[1]
    dec_s = cells[2].replace("$+$", "+").replace("$-$", "-")
    z = cells[3].strip("$ ")
    float(z)
    rows.append((name, ra_s, dec_s, z, block))

n_final = sum(r[4] == "final" for r in rows)
assert len(rows) == 12 and n_final == 10, (len(rows), n_final)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    for name, ra_s, dec_s, z, block in rows:
        c = SkyCoord(ra_s, dec_s, unit=(u.hourangle, u.deg))
        notes = []
        if block == "candidate":
            notes.append("possible candidate (broad-line SNR<5), not in final AGN sample")
        if name in alias:
            notes.append(alias[name])
        w.writerow([name, f"{c.ra.deg:.6f}", f"{c.dec.deg:.6f}", z, "spec", name.split("_")[0], "", "NIRSpec",
                    "1" if block == "final" else "", "; ".join(notes)])
print(f"wrote {out} ({len(rows)} rows: {n_final} final BL AGN + {len(rows) - n_final} candidates)")
