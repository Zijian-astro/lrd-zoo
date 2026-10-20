"""Build objects.csv for Barro et al. 2025 ("From The Cliff to Virgil": 118 LRDs with NIRSpec/PRISM spectra).

Raw files: GitHub https://github.com/guillermobc/Barro25 (commit e70d8ac577), linked from Table 2 of the paper
  Barro25_LRD_NIRSpec_bestfit_properties.fits   118 rows: DJA_ID, ra, dec, zspec, ... (Table 2 in full)
  (Barro25_LRD_NIRSpec_MBB_properties.fits has the same rows but one placeholder ID '-99--99'; not used.)
The arXiv LaTeX excerpt of Table 2 (src/tab2.tex, 8 rows) is checked against the FITS file.
field = survey field derived from the DJA root in DJA_ID (mapping below; checked to cluster on the sky).

Usage: python ingest.py <dir with the FITS file and src/tab2.tex>
"""
import csv
import re
import sys
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table

raw = Path(sys.argv[1])
t = Table.read(raw / "Barro25_LRD_NIRSpec_bestfit_properties.fits")
assert len(t) == 118


def s(x):
    return x.decode().strip() if isinstance(x, bytes) else str(x).strip()


ids = [s(x) for x in t["DJA_ID"]]
assert len(set(ids)) == 118

# check against the LaTeX excerpt of Table 2
tex = (raw / "src" / "tab2.tex").read_text()
ex = re.findall(r"^([a-z0-9-]+-\d+) & ([0-9.]+) & ([-0-9.]+) & ([0-9.]+) &", tex, re.M)
assert len(ex) == 8
for name, ra, dec, z in ex:
    r = t[ids.index(name)]
    assert f"{float(r['ra']):.6f}" == ra and f"{float(r['dec']):.6f}" == dec and f"{float(r['zspec']):.3f}" == z, name

FIELD_PREFIXES = [
    ("capers-cos", "COSMOS"), ("cosmos-transients", "COSMOS"),
    ("capers-egs", "EGS"), ("ceers", "EGS"), ("egs-nelson", "EGS"), ("rubies-egs", "EGS"),
    ("capers-uds", "UDS"), ("gto-wide-uds", "UDS"), ("mom-uds", "UDS"), ("rubies-uds", "UDS"),
    ("jades-gdn", "GOODS-N"), ("gds-", "GOODS-S"), ("jades-gds", "GOODS-S"),
    ("uncover", "Abell 2744"), ("abell2744", "Abell 2744"),
]


def field_of(dja_id):
    for p, f in FIELD_PREFIXES:
        if dja_id.startswith(p):
            return f
    raise ValueError(dja_id)


rows = [[i, f"{float(r['ra']):.6f}", f"{float(r['dec']):.6f}", f"{float(r['zspec']):.4f}", "spec", field_of(i), "1",
         "NIRSpec/PRISM"] for i, r in zip(ids, t)]
for f in {x[5] for x in rows}:
    c = SkyCoord([float(x[1]) for x in rows if x[5] == f] * u.deg, [float(x[2]) for x in rows if x[5] == f] * u.deg)
    cen = SkyCoord(np.median(c.ra.deg) * u.deg, np.median(c.dec.deg) * u.deg)
    assert c.separation(cen).deg.max() < 0.5, f

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
