"""Build objects.csv for Ananna et al. 2024 (ApJL 969, L18; arXiv:2404.19010),
"X-ray View of Little Red Dots: Do They Host Supermassive Black Holes?".

Raw file: arxiv_2404.19010.src (arXiv LaTeX source, tar.gz, v2)
  Table 1 (tab:sample, "Analyzed sample of Little Red Dots"): 23 rows in Abell 2744 with RA/Dec in
  decimal degrees (UNCOVER IDs); rows commented out with '%' in the source are not part of the
  published table and are skipped. All LRDs are undetected individually in Chandra (xray=nondet;
  the table gives only L_2-10keV upper limits).
  Markers: z* = spectroscopic (Greene+23); dagger = triply lensed quasar images (only ID 8296 used
  in the stack); double dagger = Labbe+23 AGN subset.

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2404.19010.src") as tf:
    tex = tf.extractfile("main.tex").read().decode("utf-8")
assert "None of the LRDs are det" in tex

seg = tex[tex.index(r"\caption{\textcolor{black}{Analyzed sample of Little Red Dots.}}"):tex.index(r"\label{tab:sample}")]
seg = seg[seg.index("(10)"):]
seg = seg[seg.index(r"\hline") + len(r"\hline"):]
seg = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in seg.splitlines())

rows = []
for row in seg.split(r"\\"):
    row = row.replace(r"\hline", "").strip()
    if not row:
        continue
    c = [x.strip() for x in row.split("&")]
    assert len(c) == 10, c
    m = re.fullmatch(r"(\d+)(?:\$\^\{?(.*?)\}?\$)?", c[0])
    uid, marks = m.group(1), m.group(2) or ""
    ra = c[1]
    dec = c[2].replace("$-$", "-").replace("$", "").strip()
    zm = re.fullmatch(r"([\d.]+)(\$\^\{\\rm\s*\\star\}\$)?", c[3].replace("\t", " ").replace(" ", ""))
    z, zspec = zm.group(1), bool(zm.group(2))
    lx = c[6].replace("$", "")
    notes = [f"UNCOVER ID {uid}", f"mu={c[4]}", f"log L2-10keV {lx}"]
    if r"\ddagger" in marks:
        notes.append("Labbe+23 AGN subset")
    if r"\dagger" in marks.replace(r"\ddagger", ""):
        notes.append("image of the triply lensed quasar (Furtak+23)" + ("; used in stack" if uid == "8296" else "; not stacked"))
    rows.append([f"UNCOVER-{uid}", ra, dec, z, "spec" if zspec else "phot", "Abell 2744", "1", "nondet",
                 "; ".join(notes)])
assert len(rows) == 23, len(rows)
assert sum("triply" in r[-1] for r in rows) == 3
assert sum("AGN subset" in r[-1] for r in rows) == 14  # 12 galaxies, the lensed quasar counted 3x

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "xray", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows)")
