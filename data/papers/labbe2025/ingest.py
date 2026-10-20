"""Build objects.csv for Labbe et al. 2025, ApJ 978, 92 (arXiv:2306.07320), UNCOVER candidate red AGN in Abell 2744.

Raw file: arXiv LaTeX source (https://arxiv.org/e-print/2306.07320, v1, the only arXiv version), extracted to
  <dir>/arxiv_src/main.tex. No VizieR catalogue or journal MRT exists; we parse the deluxetable
  "Sample" (label table:thesample), which lists every object satisfying (red1 | red2) & compact with
  columns: UNCOVER ID, RA, Dec, z_phot (AGN-only fit), mu, Main flag, SED flag, F444W, colours, r_e, ...

Usage: python ingest.py <raw dir containing arxiv_src/main.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "arxiv_src" / "main.tex").read_text()
blk = tex[tex.index(r"\label{table:thesample}"):]
blk = blk[blk.index(r"\startdata") + len(r"\startdata"):blk.index(r"\enddata")]

rows = []
for line in blk.splitlines():
    line = line.strip()
    if not line or line.startswith("%"):
        continue
    p = [x.strip() for x in line.rstrip("\\").split("&")]
    assert len(p) == 13, line
    uid = int(p[0])
    ra = float(p[1])
    dec = float(p[2].replace("$-$", "-"))
    zphot, mu = float(p[3]), float(p[4])
    main, sed = int(p[5]), int(p[6])
    assert main in (0, 1) and sed in (0, 1) and (sed <= main)
    rows.append((uid, p[1], p[2].replace("$-$", "-"), ra, dec, p[3], mu, main, sed, p[7]))

# Paper: Main (point-source dominated) sample = 26 LRDs, SED subsample = 17.
assert len(rows) == 35, len(rows)
assert sum(r[7] for r in rows) == 26 and sum(r[8] for r in rows) == 17
assert len({r[0] for r in rows}) == len(rows)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "f444w", "notes"])
    for uid, ra_s, dec_s, ra, dec, z, mu, main, sed, f444 in rows:
        if main:
            note = "Main sample (point-source dominated)" + ("; SED subsample (AGN-dominated at F444W)" if sed else "")
        else:
            note = "Parent sample only: not point-source dominated, excluded from the Main sample"
        w.writerow([f"UNCOVER-{uid}", ra_s, dec_s, z, "phot", "Abell 2744", str(main), f444, f"{note}; mu={mu:g}"])
print(f"wrote {out} ({len(rows)} rows, {sum(r[7] for r in rows)} Main/LRD, {sum(r[8] for r in rows)} SED)")
