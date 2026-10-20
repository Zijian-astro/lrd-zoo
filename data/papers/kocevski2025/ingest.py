"""Build objects.csv for Kocevski et al. 2025, ApJ 986, 126 (arXiv:2404.03576).

Raw files (journal machine-readable tables, ApJ 986/2/126 revision1):
  journal/apjadbc7dt3_mrt.txt  Table 3: primary sample of 341 little red dots
      https://content.cld.iop.org/journals/0004-637X/986/2/126/revision1/apjadbc7dt3_mrt.txt
  journal/apjadbc7dt5_mrt.txt  Table 5: 15 LRDs with new RUBIES NIRSpec/G395M broad-line detections
      https://content.cld.iop.org/journals/0004-637X/986/2/126/revision1/apjadbc7dt5_mrt.txt
Optional cross-check (used only if present):
  github/Kocevski24.Table3.dat  the authors' GitHub copy of Table 3
      https://github.com/dalekocevski/Kocevski24 (commit b47c1872e4a5133656eade1dbfbc52db8124a40d)

Usage: python ingest.py <raw dir containing journal/ (and optionally github/)>
"""
import csv
import sys
from collections import Counter
from pathlib import Path

from astropy.io import ascii

raw = Path(sys.argv[1])
t3 = ascii.read(raw / "journal" / "apjadbc7dt3_mrt.txt", format="cds")
t5 = ascii.read(raw / "journal" / "apjadbc7dt5_mrt.txt", format="cds")
assert len(t3) == 341, len(t3)
assert len(t5) == 15, len(t5)

# Survey prefix of the ID -> sky field (paper Table 1: survey / field)
FIELD = {"CEERS": "EGS", "PRIMER-UDS": "UDS", "PRIMER-COS": "COSMOS",
         "JADES": "GOODS-S", "NGDEEP": "GOODS-S", "UNCOVER": "Abell 2744"}
prefixes = Counter(str(r["ID"]).split()[0] for r in t3)
# per-survey counts quoted in Sect. 4 of the paper
assert prefixes == {"PRIMER-UDS": 117, "PRIMER-COS": 81, "CEERS": 64, "JADES": 46, "UNCOVER": 23, "NGDEEP": 10}, prefixes
assert len(set(t3["ID"])) == 341

# Table 5: broad lines from RUBIES G395M spectra; check each is in Table 3 at the same position
by_id = {str(r["ID"]): r for r in t3}
bl_ids = set()
for r in t5:
    p = by_id[str(r["ID"])]
    assert abs(p["RAdeg"] - r["RAdeg"]) < 2e-5 and abs(p["DEdeg"] - r["DEdeg"]) < 2e-5, r["ID"]
    bl_ids.add(str(r["ID"]))

# Optional: the GitHub copy must agree on position, redshift and flag (GitHub zflag: 0=phot, 1=spec)
gh_file = raw / "github" / "Kocevski24.Table3.dat"
if gh_file.exists():
    gh = {}
    for line in gh_file.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            p = line.split()
            gh[p[0] + " " + p[1]] = p[2:]
    assert set(gh) == set(by_id)
    for i, r in by_id.items():
        g = gh[i]
        assert abs(float(g[0]) - r["RAdeg"]) < 1e-6 and abs(float(g[1]) - r["DEdeg"]) < 1e-6, i
        assert abs(float(g[2]) - r["zbest"]) < 1e-6 and int(g[3]) + 1 == r["zflag"], i

ZTYPE = {1: "phot", 2: "spec"}
out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "spec", "broad_line", "f444w"])
    for r in t3:
        i = str(r["ID"])
        bl = i in bl_ids
        w.writerow([i, f"{r['RAdeg']:.6f}", f"{r['DEdeg']:.6f}", f"{r['zbest']:.2f}", ZTYPE[int(r["zflag"])],
                    FIELD[i.split()[0]], "NIRSpec/grating" if bl else "", "1" if bl else "",
                    f"{r['F444Wmag']:.2f}"])
print(f"wrote {out} ({len(t3)} rows, {len(bl_ids)} with broad lines)")
