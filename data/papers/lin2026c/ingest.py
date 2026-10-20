"""Build objects.csv for Lin, X. et al. 2026, (LRDs)^2 II: 27 low-redshift LRDs from DESI DR1.

Raw files: Zenodo record 20309303 (https://doi.org/10.5281/zenodo.20309303)
  master_table.ecsv   27 LRDs x 112 columns (shortname, iau_name, tier, targetid, ra_deg, dec_deg, z, ...)
  README.md

Coordinates: the catalogue's ra_deg/dec_deg are rounded to ~6 significant digits (up to 1.6 arcsec off), so
RA/Dec are taken from the full IAU names (e.g. J012930.87+062843.32, 0.01 s / 0.01 arcsec precision),
converted with astropy SkyCoord, and asserted to agree with ra_deg/dec_deg to < 2 arcsec.
Variability: the abstract reports robust long-term variability only for J1717+3807 -> variable=1 there.

Usage: python ingest.py <dir with master_table.ecsv>
"""
import csv
import sys
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table

raw = Path(sys.argv[1])
t = Table.read(raw / "master_table.ecsv", format="ascii.ecsv")
assert len(t) == 27


def from_iau(name):
    n = name[1:]
    sgn = "+" if "+" in n else "-"
    a, b = n.split(sgn)
    return SkyCoord(f"{a[0:2]}h{a[2:4]}m{a[4:]}s", f"{sgn}{b[0:2]}d{b[2:4]}m{b[4:]}s", frame="icrs")


rows = []
for r in t:
    c = from_iau(str(r["iau_name"]))
    assert c.separation(SkyCoord(float(r["ra_deg"]) * u.deg, float(r["dec_deg"]) * u.deg)).arcsec < 2.0, r["iau_name"]
    short = str(r["shortname"])
    bl = "1" if (r["FWHM_Ha_broad"] == r["FWHM_Ha_broad"] or r["FWHM_Hb_broad"] == r["FWHM_Hb_broad"]) else ""
    rows.append([short, f"{c.ra.deg:.6f}", f"{c.dec.deg:.6f}", f"{float(r['z']):.4f}", "spec", "DESI", "1", "ground",
                 bl, "1" if short == "J1717+3807" else "",
                 f"DESI {r['iau_name']}; TARGETID {r['targetid']}; {r['tier']} tier"])

assert "J1717+3807" in [x[0] for x in rows]
out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "variable", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
