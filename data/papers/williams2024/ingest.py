"""Build objects.csv for Williams et al. 2024 (ApJ 968, 34; arXiv:2311.07483),
"The galaxies missed by Hubble and ALMA: the contribution of extremely red galaxies to the cosmic
census at 3<z<8".

Raw file: arxiv_2311.07483.src (arXiv LaTeX source, tar.gz, v1 = submitted version; no later arXiv version)
  Table tab:MIRI    30 H-dropouts inside the MIRI SMILES footprint
  Table tab:NIRCAM  37 H-dropouts without MIRI data
  Columns: JADES DR1 ID, RA, Dec (deg), F444W, photo-z, spec-z (j = JADES NIRSpec, k = FRESCO),
  ..., LRD flag (1 = meets the LRD colour selection).
ID 189494 is printed in both tables with identical values; it is kept once (from tab:MIRI).

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2311.07483.src") as tf:
    tex = tf.extractfile("manu.tex").read().decode("utf-8")


def table_rows(label):
    seg = tex[tex.index(label):]
    seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
    seg = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in seg.splitlines())
    return [[c.strip() for c in row.split("&")] for row in seg.split(r"\\") if row.strip()]


SPECZ_SRC = {"j": "JADES NIRSpec", "k": "FRESCO"}
rows, seen = [], {}
for label, where in ((r"\label{tab:MIRI}", "MIRI SMILES footprint"), (r"\label{tab:NIRCAM}", "no MIRI data")):
    tab = table_rows(label)
    print(f"{label}: {len(tab)} rows")
    for c in tab:
        assert len(c) == 12, c
        jid = c[0]
        if jid in seen:
            assert seen[jid][:6] == c[:6], (seen[jid], c)
            continue
        seen[jid] = c
        notes = [f"JADES DR1 ID {jid}", where]
        if c[5] != r"\nodata":
            m = re.fullmatch(r"([\d.]+)\$\^\{(\w)\}\$", c[5])
            z, ztype = m.group(1), "spec"
            notes.append(f"spec-z from {SPECZ_SRC[m.group(2)]}; photo-z {c[4]}")
        else:
            z, ztype = c[4], "phot"
        assert c[11] in ("0", "1")
        rows.append([f"JADES-{jid}", c[1], c[2], z, ztype, "GOODS-S", c[11], c[3], "; ".join(notes)])
dups = 30 + 37 - len(rows)
assert dups == 1, dups
rows[[r[0] for r in rows].index("JADES-189494")][-1] += "; listed in both tab:MIRI and tab:NIRCAM (arXiv v1)"
# Section 2: "For the second source ID 132229 however ... the redshift is tentative"
assert "For the second source ID 132229 however" in tex and "the redshift is tentative" in tex
rows[[r[0] for r in rows].index("JADES-132229")][-1] += " (tentative, [OIII] only)"

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "f444w", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows, {sum(r[6] == '1' for r in rows)} LRDs)")
