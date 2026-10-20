"""Build objects.csv for Pan et al. 2026 (NEXUS: spectroscopic sample of 36 LRDs from NIRSpec MSA/PRISM).

Raw files: arXiv:2606.09721 LaTeX source (https://arxiv.org/e-print/2606.09721, v1), extracted to <dir>/src/
  nexus_prism_LRD.tex, Table 2 (tab:catalog, "Spectroscopic LRD Sample"): QDR ID, R.A., Decl. (deg),
  z_spec, m_F444W, broad-line FWHM (\\nodata for 4 objects), ..., Shape, Selection flag.
broad_line = 1 where a broad-line FWHM is listed, empty where it is \\nodata.
id = "NEXUS-<QDR ID>".

Usage: python ingest.py <dir containing src/nexus_prism_LRD.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "nexus_prism_LRD.tex").read_text()
i0 = tex.index(r"\tablecaption{Spectroscopic LRD Sample}")
body = tex[tex.index(r"\startdata", i0) + len(r"\startdata"):tex.index(r"\enddata", i0)]
rows = []
for line in body.split(r"\\"):
    line = line.strip()
    if not line:
        continue
    c = [x.strip() for x in line.split("&")]
    assert len(c) == 13, c
    qdr, ra, dec, z, m444, fwhm, lha, muv, shape, sel = c[:10]
    assert re.fullmatch(r"\d+", qdr) and re.fullmatch(r"\d+\.\d{6}", ra) and re.fullmatch(r"\d+\.\d{6}", dec)
    bl = "" if fwhm == r"\nodata" else "1"
    fw = "" if fwhm == r"\nodata" else re.match(r"\$(\d+)\\pm", fwhm).group(1)
    note = f"{shape}; selection flag {sel}" + (f"; broad-line FWHM {fw} km/s" if fw else "; no broad-line FWHM listed")
    rows.append([f"NEXUS-{qdr}", ra, dec, z, "spec", "NEXUS", "1", "NIRSpec/PRISM", bl, m444, note])
assert len(rows) == 36, len(rows)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows, {sum(r[8] == '1' for r in rows)} with broad-line FWHM)")
