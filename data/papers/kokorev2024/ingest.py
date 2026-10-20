"""Build objects.csv for Kokorev et al. 2024, ApJ 968, 38 (arXiv:2401.09981).

Raw file: the full source table cited in the paper (Appendix table, "full version" link),
  Zenodo record 10820724 (https://doi.org/10.5281/zenodo.10820724), file VasilyKokorev/lrd_phot-v1.1.zip
  (md5 ea820bbd6a378d9997efe2107913259c), which contains lrd_table_v1.1.fits (260 LRDs).
  The same FITS file is on https://github.com/VasilyKokorev/lrd_phot (byte-identical).

Usage: python ingest.py <raw dir containing zenodo/lrd_phot-v1.1.zip>
"""
import csv
import io
import math
import sys
import zipfile
from collections import Counter
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord, search_around_sky
from astropy.table import Table

raw = Path(sys.argv[1])
with zipfile.ZipFile(raw / "zenodo" / "lrd_phot-v1.1.zip") as z:
    name = [n for n in z.namelist() if n.endswith("lrd_table_v1.1.fits")]
    assert len(name) == 1, name
    t = Table.read(io.BytesIO(z.read(name[0])), format="fits")
assert len(t) == 260, len(t)

# FITS 'field' value -> (ID prefix as printed in the paper's Appendix table / Table 1, sky field)
FIELD = {
    "ceers-full": ("CEERS", "EGS"),
    "primer-cosmos-east": ("PRIMER-COSMOS", "COSMOS"),
    "primer-cosmos-west": ("PRIMER-COSMOS", "COSMOS"),
    "primer-uds-north": ("PRIMER-UDS", "UDS"),
    "primer-uds-south": ("PRIMER-UDS", "UDS"),
    "gds": ("GOODS-S", "GOODS-S"),
}
fields = Counter(str(x).strip() for x in t["field"])
assert set(fields) == set(FIELD), fields

rows = []
for r in t:
    fld = str(r["field"]).strip()
    prefix, sky = FIELD[fld]
    flux = float(r["f444w_flux"])  # total flux density, uJy (AB zeropoint 23.9)
    f444w = f"{23.9 - 2.5 * math.log10(flux):.2f}" if flux > 0 else ""
    rows.append([f"{prefix}-{int(r['id'])}", f"{float(r['ra']):.7f}", f"{float(r['dec']):.7f}",
                 f"{float(r['z_phot']):.2f}", "phot", sky, f444w, [f"mosaic {fld}"]])
assert len({x[0] for x in rows}) == len(rows), "IDs not unique"

# The released table lists some sources twice: once from each half of an overlapping mosaic pair
# (primer-uds-north/south, primer-cosmos-east/west), with different IDs and positions within ~0.003 arcsec.
# Keep both rows as published and cross-reference them in notes.
c = SkyCoord(np.asarray(t["ra"], float) * u.deg, np.asarray(t["dec"], float) * u.deg)
i1, i2, sep, _ = search_around_sky(c, c, 0.05 * u.arcsec)
dup_pairs = [(a, b, s) for a, b, s in zip(i1, i2, sep.arcsec) if a < b]
for a, b, s in dup_pairs:
    assert rows[a][0].split("-")[0] == rows[b][0].split("-")[0]  # same survey, different mosaic half
    rows[a][7].append(f"same source as {rows[b][0]} (listed twice in the released table, {s:.4f} arcsec apart)")
    rows[b][7].append(f"same source as {rows[a][0]} (listed twice in the released table, {s:.4f} arcsec apart)")
assert len(dup_pairs) == 22, len(dup_pairs)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "f444w", "notes"])
    for x in rows:
        w.writerow(x[:7] + ["; ".join(x[7])])
print(f"wrote {out} ({len(rows)} rows, {len(dup_pairs)} duplicate pairs -> {len(rows) - len(dup_pairs)} unique; "
      f"{dict(fields)})")
