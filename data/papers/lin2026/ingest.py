"""Build objects.csv for Lin, X. et al. 2026 (three local LRDs at z=0.10-0.22 selected from SDSS).

Raw files: arXiv:2507.10659 LaTeX source (https://arxiv.org/e-print/2507.10659, v2), extracted to <dir>/src/
  04_OverviewProperties.tex, Table 1 (tab:basic_properties): Name, RA, DEC, z (systemic, narrow [OIII]).
  Short names (J1025+1402 etc.) from the macros in main.tex.

Usage: python ingest.py <dir containing src/04_OverviewProperties.tex>
"""
import csv
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
tex = (src / "04_OverviewProperties.tex").read_text()


def row(label):
    m = re.search(r"^" + re.escape(label) + r" & (.+?) \\\\\s*$", tex, re.M)
    return [c.strip() for c in m.group(1).split("&")]


names, ras, decs, zs = row("Name"), row("RA"), row("DEC"), row("$z$")
assert len(names) == len(ras) == len(decs) == len(zs) == 3
main = (src / "main.tex").read_text()
short = re.findall(r"\\newcommand\{\\obj[abc]\}\{(J[0-9+-]+)\}", main)
assert [s[:5] + s[10:15] for s in names] == short, (names, short)
# X-ray (Sect. "X-ray and Radio"): J1025 Chandra upper limit; J1047 <~2 sigma (not significant); J1022 no Chandra data
XRAY = {"J1025+1402": "nondet", "J1047+0739": "nondet", "J1022+0841": ""}

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "variable", "notes"])
    for n, s, ra, dec, z in zip(names, short, ras, decs, zs):
        note = f"SDSS {n}"
        if s == "J1025+1402":
            # Table 1 DEC (14.03586) is 1.8 arcsec north of the position implied by the SDSS name in the same table
            # (+14:02:07.3 = 14.03536); SDSS DR18 PhotoObj 1237664132626776244 is at 156.376211, 14.035378.
            # Keep the published table value, flag it.
            assert dec == "14.03586"
            note += ("; nicknamed 'The Egg'; NOTE Table 1 DEC is 1.8 arcsec off the SDSS-name position "
                     "(SDSS DR18: 156.376211 14.035378) - likely a typo in the paper")
        w.writerow([s, ra, dec, z, "spec", "SDSS", "1", "ground", "1", XRAY[s], "0", note])
print(f"wrote {out}: {list(zip(short, ras, decs, zs))}")
