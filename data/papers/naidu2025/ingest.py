"""Build objects.csv for Naidu et al. 2025 (MoM-BH*-1, "black hole star" at z=7.7569).

Raw files: arXiv:2503.16596 LaTeX source (https://arxiv.org/e-print/2503.16596), extracted to <dir>/src/
  ms.tex, Extended Data Table 1 ("Summary of key properties"): R.A. [deg], Dec. [deg], Redshift.
  F444W=25.4 mag from the main text.

Usage: python ingest.py <dir containing src/ms.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "ms.tex").read_text()
ra = re.search(r"R\.A\. \[deg\] & ([0-9.]+)\\\\", tex).group(1)
dec = re.search(r"Dec\. \[deg\] & \$(-?[0-9.]+)\$\\\\", tex).group(1)
z = re.search(r"Redshift & \$([0-9.]+)\^", tex).group(1)
assert "F444W$=25.4$ mag" in tex and "MoM-BH*-1" in tex

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w", "notes"])
    w.writerow(["MoM-BH*-1", ra, dec, z, "spec", "UDS", "1", "NIRSpec", "1", "25.4",
                "'black hole star'; called MoM-150135 in early versions of other papers; NIRSpec PRISM (MoM, GO-5224) + "
                "G395M (EXCELS); hint of 30% brightening in 56 d at 3-5 um (different instruments)"])
print(f"wrote {out}: MoM-BH*-1 {ra} {dec} z={z}")
