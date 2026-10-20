"""Build objects.csv for Lin, R. et al. 2026 (ZTF optical variability of seven local LRD analogs at z~0.3).

Raw files: arXiv:2603.01473 LaTeX source (https://arxiv.org/e-print/2603.01473, v3), extracted to <dir>/src/
  sf_infuplim.tex, Table 1 (tab:para): Name, R.A., Dec. (deg, 4 decimals), z_spec, ZTF variability.
  The seven objects are the V-shaped broad-line green peas of Lin, R. et al. 2025 (ApJL 980, L34).
Variability (Sect. Methods/abstract): J092834+292136 and J115438+065025 show significant excess variance in
all three ZTF bands and are fitted with a DRW model -> variable=1; J120052+331238 has non-zero excess
variance in all bands but no DRW fit -> left empty; the other four show no detectable variability -> 0.

Usage: python ingest.py <dir containing src/sf_infuplim.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "sf_infuplim.tex").read_text()
rows = re.findall(r"^(J\d{6}[+-]\d{6}) & ([0-9.]+) & (-?[0-9.]+) & +([0-9.]+) &", tex, re.M)   # skips commented rows
assert len(rows) == 7, rows
VAR = {"J092834+292136": "1", "J115438+065025": "1", "J120052+331238": ""}

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "variable", "notes"])
    for name, ra, dec, z in rows:
        note = "V-shaped broad-line green pea (local LRD analog)"
        if name == "J120052+331238":
            note += "; non-zero ZTF excess variance in g,r,i but no DRW fit"
        w.writerow([name, ra, dec, z, "spec", "SDSS/LAMOST", "1", "ground", "1", VAR.get(name, "0"), note])
print(f"wrote {out} ({len(rows)} rows)")
