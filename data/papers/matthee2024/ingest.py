"""Build objects.csv for Matthee et al. 2024 (EIGER + FRESCO NIRCam-grism broad-Halpha emitters, "Little Red Dots").

Raw file: arXiv LaTeX source of 2306.05448 (https://arxiv.org/e-print/2306.05448, v3 = accepted version), saved as
  arxiv_2306.05448.tar.gz   (member ms.tex is read directly from the tarball)

Tables used:
  tab:LRDsample  "Coordinates and redshifts of the 20 BL Halpha emitters" (sexagesimal J2000 RA/Dec, z_spec)
  tab:linefits   "Properties of the broad Halpha line emitters"; its LW-magnitude column is F444W for the FRESCO
                 (GOODS) objects and F356W for the EIGER objects, so f444w is filled for GOODS rows only.
Sexagesimal -> degrees with astropy SkyCoord.

Usage: python ingest.py <dir containing arxiv_2306.05448.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2306.05448.tar.gz") as tf:
    tex = tf.extractfile("ms.tex").read().decode("utf-8")


def tabular_rows(label):
    """Rows of the tabular in the table environment that carries \\label{<label>} (data rows after the header)."""
    i = tex.index(r"\label{" + label + "}")
    beg = tex.rindex(r"\begin{tabular}", 0, i)
    body = tex[beg:tex.index(r"\end{tabular}", beg)]
    body = body.split(r"\hline", 1)[1]          # drop the header line
    rows = []
    for line in body.split(r"\\"):
        line = re.sub(r"(?m)%.*$", "", line).replace(r"\hline", "").strip()
        if line:
            rows.append([c.strip() for c in line.split("&")])
    return rows


coords = tabular_rows("tab:LRDsample")
props = {r[0]: r for r in tabular_rows("tab:linefits")}
assert len(coords) == 20 and len(props) == 20 and set(props) == {r[0] for r in coords}

# survey fields as named in the paper text (Sect. 2): four EIGER quasar fields + the two FRESCO GOODS fields
qso_fields = {"J0100": "J0100+2802", "J1148": "J1148+5251", "J1120": "J1120+0641", "J0148": "J0148+0600"}
for name in qso_fields.values():
    assert name in tex, name

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w"])
    for oid, ra_s, dec_s, z in coords:
        dec_s = dec_s.replace("--", "-")      # LaTeX en-dash used as minus sign (GOODS-S-13971)
        c = SkyCoord(ra_s, dec_s, unit=(u.hourangle, u.deg), frame="icrs")
        float(z)
        if oid.startswith("GOODS-"):
            field = oid[:7]
            m = re.match(r"\$\s*([0-9.]+)\^", props[oid][5])
            f444w = m.group(1)
        else:
            field = qso_fields[oid.split("-")[0]]
            f444w = ""
        w.writerow([oid, f"{c.ra.deg:.6f}", f"{c.dec.deg:.6f}", z, "grism", field, "1", "NIRCam/grism", "1", f444w])
print(f"wrote {out} ({len(coords)} rows)")
