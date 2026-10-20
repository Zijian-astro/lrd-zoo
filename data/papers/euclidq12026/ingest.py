"""Build objects.csv for Euclid Collaboration: Bisigello et al. 2026 (Euclid Q1 LRD candidates).

Raw files: VizieR J/A+A/711/A24 (https://cdsarc.cds.unistra.fr/ftp/J/A+A/711/A24/)
  ReadMe        byte-by-byte description
  tabled1.dat   3341 LRD candidates (Table D.1 of the paper)

Field is assigned from the declination; the three Euclid Deep Fields are widely
separated and the resulting counts are asserted against the paper's table of
selection steps (tab:numbers; EDF-F 8+422, EDF-N 1+970, EDF-S 20+1920).

Usage: python ingest.py <dir with ReadMe and tabled1.dat>
"""
import csv
import sys
from pathlib import Path

from astropy.table import Table

raw = Path(sys.argv[1])
t = Table.read(raw / "tabled1.dat", format="ascii.cds", readme=str(raw / "ReadMe"))
assert len(t) == 3341, len(t)


def field(dec):
    if dec > 50:
        return "EDF-N"
    if -35 < dec < -20:
        return "EDF-F"
    if dec < -40:
        return "EDF-S"
    raise ValueError(dec)


rows = []
for r in t:
    ra, dec = float(r["RAdeg"]), float(r["DEdeg"])
    rows.append([f"EuclidQ1_{int(r['ID'])}", f"{ra:.6f}", f"{dec:.6f}", f"{float(r['z']):.2f}", "phot",
                 field(dec), "1"])

counts = {}
for row in rows:
    counts[row[5]] = counts.get(row[5], 0) + 1
assert counts == {"EDF-F": 430, "EDF-N": 971, "EDF-S": 1940}, counts

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows; {counts})")
