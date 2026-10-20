"""Build objects.csv for de Graaff et al. 2025 ("The Cliff", RUBIES-UDS-154183, z=3.548).

Raw files: arXiv:2503.16600 LaTeX source (https://arxiv.org/e-print/2503.16600), extracted to <dir>/src/
  main.tex, Sect. 2.1: "The primary object of this paper lies in the UDS field
  (R.A. 02:17:38.58; Dec. -05:07:46.79)"; Fig. 1 caption: "RUBIES-UDS-154183) at $\\zspec=3.548$".

Usage: python ingest.py <dir containing src/main.tex>
"""
import csv
import re
import sys
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

tex = (Path(sys.argv[1]) / "src" / "main.tex").read_text()
assert r"\newcommand{\ruby}{\textit{The Cliff}\xspace}" in tex
m = re.search(r"UDS field \(R\.A\. ([0-9:.]+); Dec\. ([-+0-9:.]+)\)", tex)
c = SkyCoord(m.group(1), m.group(2), unit=(u.hourangle, u.deg), frame="icrs")
assert r"(RUBIES-UDS-154183) at $\zspec=3.548$" in tex

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "notes"])
    w.writerow(["RUBIES-UDS-154183", f"{c.ra.deg:.6f}", f"{c.dec.deg:.6f}", "3.548", "spec", "UDS", "1", "NIRSpec",
                "1", "nondet", f"'The Cliff'; position {m.group(1)} {m.group(2)}; PRISM + G395M; X-UDS Chandra upper limits"])
print(f"wrote {out}: {m.group(1)} {m.group(2)} -> {c.ra.deg:.6f} {c.dec.deg:.6f}")
