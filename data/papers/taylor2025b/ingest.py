"""Build objects.csv for Taylor et al. 2025 (CAPERS-LRD-z9, broad-line LRD at z=9.288).

Raw files: arXiv:2505.04609 LaTeX source (https://arxiv.org/e-print/2505.04609, v4), extracted to <dir>/src/
  main.tex, Table "Properties of CAPERS-LRD-z9": R.A., Decl., Redshift; Sect. 2: "a.k.a. CAPERS-COSMOS-119334".

Usage: python ingest.py <dir containing src/main.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "main.tex").read_text()
assert r"\newcommand{\src}{CAPERS-LRD-z9}" in tex
ra = re.search(r"R\.A\. & ([0-9.]+) deg\\cr", tex).group(1)
dec = re.search(r"Decl\. & (-?[0-9.]+) deg\\cr", tex).group(1)
z = re.search(r"Redshift \(\$z\$\) & \$([0-9.]+)\\pm", tex).group(1)
assert r"\src{} (a.k.a.\ CAPERS-COSMOS-119334)" in tex

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    w.writerow(["CAPERS-LRD-z9", ra, dec, z, "spec", "COSMOS", "1", "NIRSpec/PRISM", "1",
                "a.k.a. CAPERS-COSMOS-119334; PRIMER-COSMOS imaging; broad Hbeta"])
print(f"wrote {out}: CAPERS-LRD-z9 {ra} {dec} z={z}")
