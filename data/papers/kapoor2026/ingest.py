"""Build objects.csv for Kapoor et al. 2026 (EIGER: broad-line emitters / LRDs at z~2 from NIRCam WFSS).

Raw files: arXiv:2607.00084 LaTeX source (https://arxiv.org/e-print/2607.00084, v1), extracted to <dir>/src/
  aanda.tex, Table 1 (tab:spectral): 19 broad-line emitters in two blocks, 'LRDs' (5) and 'Non-LRDs' (14),
  with ID, z_spec, sexagesimal R.A./Dec., line, ..., QSO / X-rays / HeI-outflow check marks.
RA/Dec converted with astropy SkyCoord. lrd = 1 for the LRD block, 0 for the non-LRD block.
xray = 'det' where the X-rays column has a check mark, empty otherwise (the table does not list non-detections).
field = the quasar-field prefix of the ID (EIGER/ASPIRE-type quasar fields) as written in the paper.

Usage: python ingest.py <dir containing src/aanda.tex>
"""
import csv
import re
import sys
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

tex = (Path(sys.argv[1]) / "src" / "aanda.tex").read_text()
i0 = tex.index(r"\label{tab:spectral}")
body = tex[tex.index(r"\bf LRDs", i0):tex.index(r"\end{tabular}", i0)]
lrd_part, non_part = body.split(r"\bf Non-LRDs")
rows = []
for part, flag in [(lrd_part, "1"), (non_part, "0")]:
    for line in part.split(r"\\"):
        c = [x.strip() for x in line.replace(r"\hline", "").split("&")]
        if len(c) != 11 or not re.match(r"J\d+\$\\_\$\d+", c[0]):
            continue
        name = c[0].replace(r"$\_$", "_")
        z, ra_s, dec_s = c[1], c[2], c[3].replace("$-$", "-")
        assert re.fullmatch(r"\d\d:\d\d:\d\d\.\d+", ra_s) and re.fullmatch(r"[+-]\d{1,2}:\d\d:\d\d\.\d+", dec_s), (ra_s, dec_s)
        co = SkyCoord(ra_s, dec_s, unit=(u.hourangle, u.deg), frame="icrs")
        xray = "det" if r"\checkmark" in c[9] else ""
        line_clean = "Pa-beta" if "Pa" in c[4] else "HeI 10830" if "He" in c[4] else "OI 8446" if "O" in c[4] else "?"
        notes = [f"position {ra_s} {dec_s}", f"line: {line_clean}"]
        if r"\checkmark" in c[8]:
            notes.append("QSO flag")
        if r"\checkmark" in c[10]:
            notes.append("HeI outflow")
        rows.append([name, f"{co.ra.deg:.6f}", f"{co.dec.deg:.6f}", z, "grism", name.split("_")[0], flag,
                     "NIRCam/grism", "1", xray, "; ".join(notes)])
assert len(rows) == 19 and sum(r[6] == "1" for r in rows) == 5, len(rows)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
