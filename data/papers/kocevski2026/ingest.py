"""Build objects.csv for Kocevski et al. 2026 (Skyfire: spectroscopic census of LRDs and broad-line AGN in CEERS/EGS).

Raw files (in the directory given as argv[1]):
  github/Table3.Kocevski26.cat  machine-readable broad-line table from https://github.com/dalekocevski/Kocevski26
                                (commit ed70d1a851, 2026-09-04): ID, RA, Dec, z, FWHM, flux, log M_BH, line, LRD flag
  arxiv_2609.00112.tar.gz       arXiv LaTeX source (v1); member main.tex, table tab_blagn
                                "Catalog of Skyfire Sources with Broad Emission Lines"
The GitHub table is used (it carries the per-object LRD flag, 0=NO 1=YES); every row is checked against the LaTeX
table (same IDs, identical RA/Dec/z strings). Both have 33 rows, although the text quotes 34 broad-line sources
(the missing one, Skyfire-549755, is a re-observation of RUBIES-EGS-28812).

Usage: python ingest.py <raw dir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2609.00112.tar.gz") as tf:
    tex = tf.extractfile("main.tex").read().decode("utf-8")

# --- LaTeX table (for cross-checking) ---
i = tex.index(r"\label{tab_blagn}")
beg = tex.rindex(r"\begin{tabular}", 0, i)
data = tex[beg:tex.index(r"\end{tabular}", beg)].split(r"\hline")[3]
latex = {}
for line in data.split(r"\\"):
    line = line.strip()
    if not line:
        continue
    cells = [c.strip() for c in line.split("&")]
    assert len(cells) == 8 and cells[0].isdigit(), cells
    latex[cells[0]] = (cells[1], cells[2], cells[3], cells[7])

# --- GitHub machine-readable table ---
rows = []
for line in (raw / "github" / "Table3.Kocevski26.cat").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    p = line.split()
    sid, ra, dec, z, line_name, lrd = p[0], p[1], p[2], p[3], p[-2], p[-1]
    assert lrd in ("0", "1") and line_name in ("Ha", "HeI", "Pg", "Pa"), p
    float(ra), float(dec), float(z)
    assert latex[sid][:3] == (ra, dec, z), (sid, latex.get(sid), (ra, dec, z))
    rows.append((sid, ra, dec, z, line_name, lrd))
assert len(rows) == 33 and {r[0] for r in rows} == set(latex), (len(rows), len(latex))

n_lrd = sum(r[5] == "1" for r in rows)
out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    for sid, ra, dec, z, line_name, lrd in rows:
        if line_name == "Ha":
            bl, note = "1", ""
        elif line_name == "HeI":
            assert "HeI" in latex[sid][3]
            bl, note = "", "broad HeI 10830 only (no broad Balmer/Paschen line reported)"
        else:
            assert "Pa" in latex[sid][3]
            bl, note = "1", "broad Paschen line (text: Pa-gamma; LaTeX table: Pa-delta)"
        w.writerow([f"Skyfire-{sid}", ra, dec, z, "spec", "EGS", lrd, "NIRSpec/grating", bl, note])
print(f"wrote {out} ({len(rows)} rows, {n_lrd} lrd=1)")
