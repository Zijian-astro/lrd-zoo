"""Build objects.csv for Yue et al. 2024 (ApJL 974, L26; arXiv:2404.13290),
"Stacking X-ray Observations of 'Little Red Dots': Implications for their AGN Properties".

Raw files:
  arxiv_2404.13290.src  arXiv LaTeX source (tar.gz, v3): Table 1 (tbl:sample, 34 broad-Halpha LRDs,
                        RA/Dec in degrees) and Table 2 (tbl:stack, Chandra field per object).
                        None of the LRDs is detected individually (>2.6 sigma) -> xray=nondet.
  crosscheck_zhang2025_unique_lrds_table.dat
                        copy of unique_lrds_table.dat from github.com/Zijian-astro/variable_LRD_candidates
                        (compilation with Kocevski+24 IDs and positions); used ONLY to flag rows whose
                        printed position belongs to a different Kocevski+24 ID (no values are taken from it).

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import ascii

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2404.13290.src") as tf:
    tex = tf.extractfile("sample631.tex").read().decode("utf-8")
assert "None of the LRDs are detected individually" in tex


def table_rows(label):
    seg = tex[tex.index(label):]
    seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
    seg = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in seg.splitlines())
    out = []
    for row in seg.split(r"\\"):
        row = row.replace(r"\hline", "").strip()
        if row:
            out.append([c.strip() for c in row.split("&")])
    return out


sample = table_rows(r"\label{tbl:sample}")
stack = table_rows(r"\label{tbl:stack}")
field = {c[0]: c[1] for c in stack if c[1] != "-"}
assert len(sample) == 34 and len(field) == 34

# Kocevski+24 positions from the cross-check compilation
cc = ascii.read(raw / "crosscheck_zhang2025_unique_lrds_table.dat", format="commented_header")
cc = cc[[("Kocevski24" in str(r)) for r in cc["ref"]]]
cc_coord = SkyCoord(cc["Ra"], cc["Dec"], unit="deg")

rows = []
nflag = 0
for c in sample:
    name = re.sub(r"\\tablenotemark\{.*?\}\}?", "", c[0]).strip()
    dagger = r"\dagger" in c[0]
    ref = re.fullmatch(r"\\citet\{(\w+)\}", c[7]).group(1)
    ra, dec = c[1], c[2]
    notes = [f"from {ref}"]
    if dagger:
        notes.append("in Kocevski+24 colour-selected subset")
    if ref == "kocevski24":
        num = int(name.split("-")[-1])
        pos = SkyCoord(float(ra), float(dec), unit="deg")
        i, sep, _ = pos.match_to_catalog_sky(cc_coord)
        assert sep.arcsec < 0.3, (name, sep.arcsec)
        other = str(cc["ID"][int(i)])
        if other.strip() != str(num):
            nflag += 1
            notes.append(f"WARNING: printed position matches Kocevski+24 ID {other}, not {num} "
                         f"(ID/z and position appear mismatched in Yue+24 Table 1)")
    rows.append([name, ra, dec, c[3], "spec", field[name], "1", "nondet", "; ".join(notes)])
assert nflag == 6, nflag

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "xray", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows, {nflag} flagged position/ID mismatches)")
