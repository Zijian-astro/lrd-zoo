"""Build objects.csv for Hviding et al. 2025 (RUBIES spectroscopic LRD census).

Raw files: Zenodo record 15528783 (https://doi.org/10.5281/zenodo.15528783)
  RUBIES-Hviding25-B1-bl.fits    80 broad-Balmer-line sources at z>3.1 (Table B.1)
  RUBIES-Hviding25-A1-lrds.fits  36 of them classified as spectroscopic LRDs (Table A.1)

Usage: python ingest.py <dir with the two FITS files>
"""
import csv
import sys
from pathlib import Path

from astropy.table import Table

raw = Path(sys.argv[1])
bl = Table.read(raw / "RUBIES-Hviding25-B1-bl.fits")
lrds = Table.read(raw / "RUBIES-Hviding25-A1-lrds.fits")
lrd_ids = {(str(r["field"]).strip(), int(r["srcid"])) for r in lrds}
assert len(lrd_ids) == 36 and lrd_ids <= {(str(r["field"]).strip(), int(r["srcid"])) for r in bl}

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w"])
    for r in bl:
        field = str(r["field"]).strip()
        key = (field, int(r["srcid"]))
        w.writerow([f"RUBIES-{field}-{int(r['srcid'])}", f"{r['ra']:.7f}", f"{r['dec']:.7f}", f"{float(r['z']):.2f}",
                    "spec", field, "1" if key in lrd_ids else "0", "NIRSpec/PRISM", "1", f"{r['m444w']:.2f}"])
print(f"wrote {out} ({len(bl)} rows, {len(lrd_ids)} LRDs)")
