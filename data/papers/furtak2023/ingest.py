"""Build objects.csv for Furtak et al. 2023 (discovery of the triply imaged red compact object A2744-QSO1).

Raw files: arXiv:2212.10531 LaTeX source (https://arxiv.org/e-print/2212.10531, v4), extracted to <dir>/src/
  main.tex, Table 1 (tab:photometry): ID ("Image~A~(8296)" etc.), R.A., Dec. (sexagesimal), fluxes in nJy.
  The paper refers to the three images as QSO1A, B and C; z_phot~7.6 (title/abstract).
  Sexagesimal -> degrees with astropy SkyCoord.

Usage: python ingest.py <dir containing src/main.tex>
"""
import csv
import re
import sys
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

tex = (Path(sys.argv[1]) / "src" / "main.tex").read_text()
assert r"We refer to these as \textit{QSO1A, B} and \textit{C}" in tex
assert r"red dropout object at  $z_{\mathrm{phot}}\simeq7.6$" in tex
rows = re.findall(r"^Image~([ABC])~\((\d+)\)\s*&\s*([0-9:.]+)\s*&\s*([-+0-9:.]+)\s*&(.*)$", tex, re.M)
assert [r[0] for r in rows] == ["A", "B", "C"], rows

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "notes"])
    for img, uid, ra, dec, rest in rows:
        cells = [c.strip() for c in rest.split("&")]
        f444w_njy = re.match(r"\$(\d+)\\pm", cells[13]).group(1)   # 14th flux column = F444W
        c = SkyCoord(ra, dec, unit=(u.hourangle, u.deg), frame="icrs")
        w.writerow([f"A2744-QSO1{img}", f"{c.ra.deg:.7f}", f"{c.dec.deg:.7f}", "7.6", "phot", "Abell 2744", "",
                    f"image {img} of the triply lensed A2744-QSO1; UNCOVER ID {uid}; position {ra} {dec}; "
                    f"F444W {f444w_njy} nJy (observed, lensed); later confirmed z_spec=7.0451 (Furtak+24)"])
        print(img, uid, ra, dec, f"{c.ra.deg:.7f}", f"{c.dec.deg:.7f}", "F444W nJy", f444w_njy)
print(f"wrote {out}")
