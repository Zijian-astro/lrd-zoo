"""Build objects.csv for Weibel et al. 2026 (photometric sample of 241 BH*-dominated LRD candidates).

Raw files: Zenodo record 20611335 (https://doi.org/10.5281/zenodo.20611335; concept DOI 10.5281/zenodo.20611334)
  W26_bhstar_dominated_sample_phot_catalog.fits   241 rows
  README.txt                                     column descriptions

z: the paper's z_spec (priority PRISM > grating > NIRCam grism > other) when available, else the eazy
photometric redshift z_phot_eazy. z_type: 'spec' for NIRSpec/other spectroscopic, 'grism' for NIRCam grism,
'phot' otherwise. f444w: AB mag from the total F444W flux f_f444w (nJy): m = 31.4 - 2.5 log10(f).
id: "W26-<field>-<SourceExtractor id>" (the catalogue id is only unique within a field).

Usage: python ingest.py <dir with the FITS file>
"""
import csv
import math
import sys
from pathlib import Path

from astropy.table import Table

raw = Path(sys.argv[1])
t = Table.read(raw / "W26_bhstar_dominated_sample_phot_catalog.fits")
assert len(t) == 241


def s(x):
    return x.decode().strip() if isinstance(x, bytes) else str(x).strip()


rows = []
nz = {"spec": 0, "grism": 0, "phot": 0}
for r in t:
    field = s(r["field"])
    zs = float(r["z_spec"])
    if zs > 0:
        if max(float(r["z_spec_prism"]), float(r["z_spec_g395m"]), float(r["z_spec_g235m"])) > 0:
            assert abs(zs - [float(r[c]) for c in ("z_spec_prism", "z_spec_g395m", "z_spec_g235m") if float(r[c]) > 0][0]) < 1e-6
            ztype = "spec"
        elif float(r["z_spec_grism"]) > 0:
            assert abs(zs - float(r["z_spec_grism"])) < 1e-6
            ztype = "grism"
        else:
            assert abs(zs - float(r["z_spec_other"])) < 1e-6
            ztype = "spec"
        z = f"{zs:.4f}"
    else:
        z, ztype = f"{float(r['z_phot_eazy']):.3f}", "phot"
    nz[ztype] += 1
    f = float(r["f_f444w"])
    mag = f"{31.4 - 2.5 * math.log10(f):.2f}" if f > 0 else ""
    notes = []
    if int(r["is_vshaped"]) == 0:
        notes.append("not V-shaped by Kokorev+24 colours")
    prog = s(r["spec_program"])
    if prog not in ("-", ""):
        notes.append(f"spec: {prog}")
    rows.append([f"W26-{field}-{int(r['id'])}", f"{float(r['ra']):.7f}", f"{float(r['dec']):.7f}", z, ztype, field,
                 "1", mag, "; ".join(notes)])

assert len({x[0] for x in rows}) == 241
out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "f444w", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows; z types {nz})")
