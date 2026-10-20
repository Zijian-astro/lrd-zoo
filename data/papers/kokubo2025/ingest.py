"""Build objects.csv for Kokubo & Harikane 2025 (ApJ 995, 24; arXiv:2407.04777),
"Challenging the AGN scenario for JWST/NIRSpec LRD and non-LRD broad Halpha emitters in light of
non-detection of NIRCam photometric variability and X-ray".

Raw file: arxiv_2407.04777.src (arXiv LaTeX source, tar.gz, v3)
  Table tbl:targets            5 broad-Halpha emitters in Abell 2744 (sexagesimal ICRS coordinates)
  Table tbl:chandra_upperlimit Chandra 2-10 keV upper limits for all five (no X-ray detection)
The paper reports no significant NIRCam variability for any of the five (variable=0).

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
with tarfile.open(raw / "arxiv_2407.04777.src") as tf:
    tex = tf.extractfile("jwst_agn_var.tex").read().decode("utf-8")


def table_rows(label):
    seg = tex[tex.index(label):]
    seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
    seg = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in seg.splitlines())
    out = []
    for row in seg.split(r"\\"):
        row = row.replace(r"\hline", "").strip()
        if row:
            out.append([c.strip() for c in row.split("&")])
    return out


targets = table_rows(r"\label{tbl:targets}")
xray = table_rows(r"\label{tbl:chandra_upperlimit}")
assert len(targets) == 5 and len(xray) == 5
xlim = {c[0].replace("~", " "): c[1] for c in xray}
assert all(v.startswith("$<") for v in xlim.values())  # upper limits only
# reference key of the table note: (1) Harikane+23, (2) Greene+24
assert r"(1) \cite{har23}; (2) \cite{gre24}" in tex
REF = {"(1)": "Harikane et al. 2023", "(2)": "Greene et al. 2024"}
assert "no significant variability in any of the objects" in tex

rows = []
for c in targets:
    name = c[0].replace("~", " ")
    c_ = SkyCoord(c[3], c[4], unit=(u.hourangle, u.deg), frame="icrs")
    lrd = {"Y": "1", "N": "0"}[c[1]]
    lx = xlim[name].replace("$", "")
    notes = (f"UNCOVER DR3 ID {c[2]}; mu={c[6]}; broad-Halpha emitter from {REF[c[10]]}; "
             f"L2-10keV(Gamma=1.7) {lx}e42 erg/s")
    rows.append([name, f"{c_.ra.deg:.7f}", f"{c_.dec.deg:.7f}", c[5], "spec", "Abell 2744", lrd,
                 "nondet", "0", notes])

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "xray", "variable", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
