"""Build objects.csv for Zhang et al. 2026 (ApJ 998, 170; arXiv:2506.04350),
"JWST Insights into Narrow-line Little Red Dots".

Raw files:
  arxiv_2506.04350.src   arXiv LaTeX source (tar.gz, v2 = accepted version); Table 1
                         "Basic Properties for the Five Narrow-line LRDs" (tab:base_info)
  narrow_lrd_info.fits   catalog/narrow_lrd_info.fits from https://github.com/Zijian-astro/NL-LRD-2025-Data
                         (DJA catalogue rows of the same five objects; used for cross-checks,
                         the DJA spectrum root/srcid and the survey field)

The paper finds no broad Halpha component in any of the five (broad_line=0) and no individual
X-ray detection in AEGIS-X Deep / X-UDS (xray=nondet, Section "X-ray Non-detection").

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

from astropy.table import Table

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2506.04350.src") as tf:
    tex = tf.extractfile("ms.tex").read().decode("utf-8")
assert "none of them has an individual X-ray detection" in tex

seg = tex[tex.index(r"\label{tab:base_info}"):]
seg = seg[seg.index(r"\hline", seg.index("(13)")):seg.index(r"\end{tabular}")]
paper = []
for row in seg.split(r"\\"):
    row = re.sub(r"(?<!\\)%.*", "", row).replace(r"\hline", "").strip()
    if not row:
        continue
    c = [x.strip() for x in row.split("&")]
    dec = c[2].replace("$", "")
    paper.append(dict(uid=int(c[0]), ra=c[1], dec=dec, z=c[3]))
assert len(paper) == 5, paper

dja = Table.read(raw / "narrow_lrd_info.fits")
dja = {int(r["uid"]): r for r in dja}
assert set(dja) == {p["uid"] for p in paper}

rows = []
for p in paper:
    d = dja[p["uid"]]
    # paper coordinates are the DJA catalogue coordinates (6 decimals)
    assert abs(float(p["ra"]) - float(d["ra"])) < 1e-6 and abs(float(p["dec"]) - float(d["dec"])) < 1e-6, (p, d["ra"], d["dec"])
    assert abs(float(p["z"]) - float(d["z"])) < 0.005, (p, d["z"])  # paper z from its own line fit
    root = str(d["root"]).strip()
    m = re.match(r"rubies-(egs|uds)\d+", root)
    field = m.group(1).upper()
    notes = f"DJA UID {p['uid']} ({str(d['jname']).strip()}); DJA spectrum {root} srcid {int(d['srcid'])}"
    rows.append([f"UID-{p['uid']}", p["ra"], p["dec"], p["z"], "spec", field, "1", "NIRSpec/grating", "0",
                 "nondet", notes])

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
