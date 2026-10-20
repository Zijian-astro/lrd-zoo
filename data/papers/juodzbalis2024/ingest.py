"""Build objects.csv for Juodzbalis et al. 2024 (GN-28074, the JADES "Rosetta Stone" AGN at z=2.26).

Raw files: arXiv:2407.08643 LaTeX source (https://arxiv.org/e-print/2407.08643), extracted to <dir>/src/
  mnras_template.tex, Introduction: "GN-28074 (RA = 189.06458, Dec = 62.27382; CANDELS ID GN-19549;
  3D-HST ID 26945) a broad line AGN at $z = 2.26$ ... in the GOODS-N field".

Usage: python ingest.py <dir containing src/mnras_template.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "mnras_template.tex").read_text()
m = re.search(r"GN-28074 \(RA = ([0-9.]+), Dec = (-?[0-9.]+); CANDELS ID (GN-[0-9]+); 3D-HST ID ([0-9]+)\) "
              r"a broad line AGN at \$z = ([0-9.]+)\$", tex)
ra, dec, candels, hst3d, z = m.groups()

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "notes"])
    w.writerow(["GN-28074", ra, dec, z, "spec", "GOODS-N", "", "NIRSpec", "1", "nondet",
                f"CANDELS ID {candels}; 3D-HST ID {hst3d}; JADES PRISM + R1000 gratings; Balmer/HeI absorption; "
                "paper calls it a broad-line AGN with LRD-like colours and v-shaped continuum (not explicitly an LRD)"])
print(f"wrote {out}: GN-28074 {ra} {dec} z={z}")
