"""Build objects.csv for de Graaff et al. 2026 (DJA/NIRSpec LRD sample: "LRDs host Black Hole Stars").

Raw files: Zenodo record 21977747 (https://doi.org/10.5281/zenodo.21977747; MNRAS version of the table,
concept DOI 10.5281/zenodo.17665942)
  deGraaff2026_mnras_lrds_withdups_blackbody_eline_fits.fits   181 PRISM spectra of 146 unique LRDs
  README.txt

Rows written:
  * the 146 rows with use_dG26 == True (one per unique source, highest-S/N PRISM spectrum), plus
  * non-use rows lying > 0.3 arcsec from every use row, i.e. additional lensed images at different
    positions (asserted to be exactly 2: images of UNCOVER 13123 = A2744-QSO1).
  The remaining 33 non-use rows are duplicate spectra of the same position (all within 0.12 arcsec of a
  use row) and are dropped.
id = "<DJA root>_<program ID>_<MSA srcid>" (the DJA spectrum file name without the disperser).
field = survey field derived from the DJA root name (mapping below).

Usage: python ingest.py <dir with the FITS file>
"""
import csv
import sys
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table

raw = Path(sys.argv[1])
t = Table.read(raw / "deGraaff2026_mnras_lrds_withdups_blackbody_eline_fits.fits")
assert len(t) == 181
use = t[t["use_dG26"]]
non = t[~t["use_dG26"]]
assert len(use) == 146 and len({(int(r["pid"]), int(r["srcid"])) for r in use}) == 146

cu = SkyCoord(use["ra"] * u.deg, use["dec"] * u.deg)
cn = SkyCoord(non["ra"] * u.deg, non["dec"] * u.deg)
idx, sep, _ = cn.match_to_catalog_sky(cu)
extra = non[sep.arcsec > 0.3]
assert np.all(sep.arcsec[sep.arcsec <= 0.3] < 0.12)
assert len(extra) == 2, len(extra)
extra_parent = {int(r["srcid"]): int(use["srcid"][i]) for r, i, s in zip(non, idx, sep.arcsec) if s > 0.3}

FIELD_PREFIXES = [  # (DJA root prefix, field)
    ("capers-cos", "COSMOS"), ("cos-barrufet", "COSMOS"), ("cosmos-transients", "COSMOS"), ("mom-cos", "COSMOS"),
    ("capers-egs", "EGS"), ("ceers", "EGS"), ("egs-nelson", "EGS"), ("gto-wide-egs", "EGS"), ("rubies-egs", "EGS"),
    ("capers-uds", "UDS"), ("gto-wide-uds", "UDS"), ("mom-uds", "UDS"), ("rubies-uds", "UDS"),
    ("diver-gdn", "GOODS-N"), ("jades-gdn", "GOODS-N"),
    ("gds-", "GOODS-S"), ("jades-gds", "GOODS-S"),
    ("uncover", "Abell 2744"), ("nexus", "NEXUS"),
    ("macs0416", "MACS0416"), ("macs0417", "MACS0417"), ("macs1423", "MACS1423"), ("macsj0647", "MACS0647"),
    ("rxj2129", "RXJ2129"),
]


def field_of(root):
    for p, f in FIELD_PREFIXES:
        if root.startswith(p):
            return f
    raise ValueError(root)


rows = []
for r, is_extra in [(r, False) for r in use] + [(r, True) for r in extra]:
    root = r["root"].decode() if isinstance(r["root"], bytes) else str(r["root"])
    pid, src = int(r["pid"]), int(r["srcid"])
    assert root.endswith("-v4")
    notes = []
    if float(r["mu"]) != 1.0:
        notes.append(f"lensed, mu={float(r['mu']):.2f}")
    if is_extra:
        notes.append(f"additional lensed image of {root.split('_')[0]}_{pid}_{extra_parent[src]} (not counted among the 146 unique sources)")
    rows.append([f"{root}_{pid}_{src}", f"{float(r['ra']):.7f}", f"{float(r['dec']):.7f}", f"{float(r['zspec']):.4f}",
                 "spec", field_of(root), "1", "NIRSpec/PRISM", "; ".join(notes)])

# sanity: every field's members cluster on the sky (catches a wrong prefix mapping)
for f in {row[5] for row in rows}:
    c = SkyCoord([float(x[1]) for x in rows if x[5] == f] * u.deg, [float(x[2]) for x in rows if x[5] == f] * u.deg)
    if f != "NEXUS":
        cen = SkyCoord(np.median(c.ra.deg) * u.deg, np.median(c.dec.deg) * u.deg)
        assert c.separation(cen).deg.max() < 1.0, f

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows: {len(use)} unique sources + {len(extra)} extra lensed images)")
