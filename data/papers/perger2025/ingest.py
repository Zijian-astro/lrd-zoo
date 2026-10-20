"""Build objects.csv for Perger et al. 2025 (A&A 693, L2; arXiv:2411.19518),
"Deep silence: Radio properties of little red dots".

Raw files: VizieR catalogue J/A+A/693/L2 (https://cdsarc.cds.unistra.fr/ftp/J/A+A/693/L2/)
  ReadMe
  stacked.dat   919 literature LRDs at Dec > -40 deg used for the VLASS/FIRST cross-match and stacking
                (Name, RAdeg, DEdeg, zspec, zphot, Ref bibcode, Notes). No LRD has a radio counterpart.

Cross-check file (used only to add WARNING notes, never values):
  crosscheck_zhang2025_unique_lrds_table.dat  copy of unique_lrds_table.dat from
                github.com/Zijian-astro/variable_LRD_candidates (Kocevski+24 IDs, positions, spec-z)

ids: the Name column as given; names that are bare numbers are prefixed with the discovery-paper
bibcode from the Ref column ("<bibcode>-<number>") so that they are unique and traceable.

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import ascii

raw = Path(sys.argv[1])
t = ascii.read(str(raw / "stacked.dat"), readme=str(raw / "ReadMe"), format="cds")
assert len(t) == 919, len(t)


def masked(col):
    return np.ma.getmaskarray(t[col])


zs_m, zp_m, n_m = masked("zspec"), masked("zphot"), masked("Notes")

# Cross-check (flags only, no values taken): Kocevski+24 positions and spec-z from the Zhang+25
# compilation (crosscheck_zhang2025_unique_lrds_table.dat, github.com/Zijian-astro/variable_LRD_candidates).
# Rows whose zspec was borrowed from Kocevski+24 ("zspec from 2024arXiv240403576K") or that come from
# Wang+24 (2024ApJ...969L..13W) are compared with the Kocevski+24 spec-z of the object at the same position.
cc = ascii.read(str(raw / "crosscheck_zhang2025_unique_lrds_table.dat"), format="commented_header")
cc = cc[(cc["zspec"] > 0) & np.array(["Kocevski24" in str(x) for x in cc["ref"]])]
cc_coord = SkyCoord(cc["Ra"], cc["Dec"], unit="deg")
LABBE_NATURE = "2023Natur.616..266L"  # photometric candidates; Perger lists their z in the zspec column

rows = []
flagged = []
for i, r in enumerate(t):
    name = str(r["Name"]).strip()
    ref = str(r["Ref"]).strip()
    note_src = "" if n_m[i] else str(r["Notes"]).strip()
    rid = f"{ref}-{name}" if re.fullmatch(r"\d+", name) else name
    zs = None if zs_m[i] else float(r["zspec"])
    zp = None if zp_m[i] else float(r["zphot"])
    notes = [f"Name {name}; ref {ref}"]
    if zs is not None:
        z, ztype = f"{zs:.5f}".rstrip("0").rstrip("."), "spec"
        if ref == LABBE_NATURE:
            ztype = ""
            notes.append("z is in Perger's zspec column but comes from Labbe+23 (Nature), a photometric study: z_type left empty")
    elif zp is not None:
        z, ztype = f"{zp:.2f}", "phot"
    else:
        z, ztype = "", ""
    if zs is not None and zp is not None:
        notes.append(f"zphot={zp:.2f}")
    if note_src:
        n = note_src
        if n == "cluster coordinates used":
            n = "WARNING: Perger+25 note 'cluster coordinates used' (position may not be the LRD's own)"
        notes.append(n)
    if zs is not None and (note_src == "zspec from 2024arXiv240403576K" or ref == "2024ApJ...969L..13W"):
        j, sep, _ = SkyCoord(float(r["RAdeg"]), float(r["DEdeg"]), unit="deg").match_to_catalog_sky(cc_coord)
        if sep.arcsec < 0.3 and abs(float(cc["zspec"][int(j)]) - zs) > 0.05:
            o = cc[int(j)]
            flagged.append(name)
            notes.append(f"WARNING: zspec {z} does not match Kocevski+24 ID {o['ID']} (spec-z {float(o['zspec']):.2f}) "
                         f"at this position; the ID/z-position pairing in this row looks wrong")
    rows.append([rid, f"{float(r['RAdeg']):.9f}", f"{float(r['DEdeg']):.9f}", z, ztype, "1", "; ".join(notes)])

ids = [r[0] for r in rows]
assert len(set(ids)) == len(ids)
assert sorted(flagged) == sorted(["RUBIES-EGS-49140", "RUBIES-EGS-55604", "48983", "nc5-9553", "22049"]), flagged

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "lrd", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows; {sum(r[4] == 'spec' for r in rows)} spec-z, "
      f"{sum(r[4] == 'phot' for r in rows)} phot-z)")
