"""Build objects.csv for Labbe et al. 2024 (A2744-45924, ultraluminous LRD at z=4.47).

Raw files: arXiv:2412.04557 LaTeX source (https://arxiv.org/e-print/2412.04557), extracted to <dir>/src/
  paper.tex, Introduction: "... is in the Abell 2744 field (R.A.=3.584758, Dec=$-$30.343630)"
  Redshift z=4.47 from the title and Sect. 2 ("at $z=4.47$").

Usage: python ingest.py <dir containing src/paper.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "paper.tex").read_text()
assert r"\newcommand{\source}{A2744$-$45924\xspace}" in tex
m = re.search(r"Abell 2744 field \(R\.A\.=([0-9.]+), Dec=\$-\$([0-9.]+)\)", tex)
ra, dec = float(m.group(1)), -float(m.group(2))
assert "Little Red Dot at z=4.47" in tex and "at $z=4.47$" in tex

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "notes"])
    w.writerow(["A2744-45924", f"{ra:.6f}", f"{dec:.6f}", "4.47", "spec", "Abell 2744", "1", "NIRSpec/PRISM", "1",
                "nondet", "UNCOVER ID 45924; F444W~22 AB; also NIRCam/grism F356W (ALT); Chandra non-detection"])
print(f"wrote {out}: A2744-45924 {ra} {dec}")
