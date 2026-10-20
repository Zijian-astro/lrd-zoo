"""Build objects.csv for Perez-Gonzalez et al. 2024 (ApJ 968, 4; arXiv:2401.08782),
"What is the nature of Little Red Dots and what is not, MIRI SMILES edition".

Raw file: arxiv_2401.08782.src (arXiv LaTeX source, tar.gz, v2)
  table_sample_v1.4.tex  Table 1 "Sample of LRDs": 31 LRDs in GOODS-S with IAU-format names
                         JADES-GS+RRR.RRRRR-DD.DDDDD (decimal degrees, 5 decimals), JADES DR2 ID,
                         F444W, colours and MIRI subsample. RA/Dec are parsed from the names (the
                         paper gives no separate coordinate columns).
  table_props_v1.4.tex   Table 2 "Physical properties" (complete version online only): the printed
                         rows give redshifts for 4 objects (1-decimal values = photometric); rows that
                         are commented out in the source are not used.

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2401.08782.src") as tf:
    sample_tex = tf.extractfile("table_sample_v1.4.tex").read().decode("utf-8")
    props_tex = tf.extractfile("table_props_v1.4.tex").read().decode("utf-8")


def data_rows(tex):
    seg = tex[tex.index(r"\startdata") + len(r"\startdata"):tex.index(r"\enddata")]
    seg = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in seg.splitlines())
    return [[c.strip() for c in row.split("&")] for row in seg.split(r"\\") if row.strip()]


# printed redshifts (Table 2); "spectroscopic values given with 4 decimals"
assert "spectroscopic values given with 4 decimals" in props_tex
zprint = {}
for c in data_rows(props_tex):
    if c[0]:
        zprint[c[0]] = c[1]
assert set(zprint) == {"42645", "57356", "68544", "70714"}, zprint

rows = []
for c in data_rows(sample_tex):
    assert len(c) == 6, c
    m = re.fullmatch(r"JADES-GS-(\d+\.\d{5})\$([+-])\$(\d+\.\d{5})", c[0])
    ra, sign, dec = m.group(1), m.group(2), m.group(3)
    dec = ("-" if sign == "-" else "") + dec
    name = f"JADES-GS-{ra}{sign}{m.group(3)}"  # as printed (LaTeX $-$ -> -)
    jid = c[1]
    f444w = re.match(r"\$([\d.]+)\\pm", c[2]).group(1)
    z = zprint.get(jid, "")
    ztype = ("spec" if len(z.split(".")[-1]) == 4 else "phot") if z else ""
    notes = f"JADES DR2 ID {jid}; MIRI subsample: {c[5]}"
    rows.append([name, ra, dec, z, ztype, "GOODS-S", "1", f444w, notes])
assert len(rows) == 31, len(rows)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "f444w", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
