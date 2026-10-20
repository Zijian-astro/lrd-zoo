"""Build objects.csv for Wang et al. 2024 (RUBIES-BLAGN-1, broad-line LRD at z=3.1034).

Raw files: arXiv:2403.02304 LaTeX source (https://arxiv.org/e-print/2403.02304), extracted to <dir>/src/
  rubies_brd_wang.tex, Table "Observations" (tab:obs): RA [deg], Dec [deg], z_spec, F444W.

Usage: python ingest.py <dir containing src/rubies_brd_wang.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "rubies_brd_wang.tex").read_text()
assert r"\newcommand{\rd}{RUBIES-BLAGN-1}" in tex
ra = re.search(r"RA \[deg\] & ([0-9.]+) \\\\", tex).group(1)
dec = re.search(r"Dec \[deg\] & (-?[0-9.]+) \\\\", tex).group(1)
z = re.search(r"\$z_\{\\rm spec\}\$ & \$([0-9.]+) \\pm", tex).group(1)
f444w = re.search(r"F444W & \$([0-9.]+) \\pm [0-9.]+\$ & JWST/NIRCam", tex).group(1)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "f444w", "notes"])
    w.writerow(["RUBIES-BLAGN-1", ra, dec, z, "spec", "UDS", "1", "NIRSpec", "1", "nondet", f444w,
                "PRISM + G395M; MIRI F770W/F1800W detected; X-ray 3-sigma upper limit"])
print(f"wrote {out}: RUBIES-BLAGN-1 {ra} {dec} z={z} F444W={f444w}")
