"""Build objects.csv for Zhuang et al. 2026 (NEXUS: NIRCam/WFSS census of broad-line AGNs and LRDs at 3<~z<~6).

Raw files: arXiv:2505.20393 LaTeX source (https://arxiv.org/e-print/2505.20393, v1), extracted to <dir>/src/
  sample631.tex, Table 1 (tab1, "Broad-line Emitter Sample"): ID, R.A., Decl. (deg), z_spec (grism), m_F444W,
  broad-line luminosity/flux/FWHM, line, log M_BH, Type, selection flag.
Type column: 'BLAGN (LRD)' / 'BLAGN (LRD*)' / 'BLAGN* (LRD*)' -> lrd=1 (15 LRDs incl. tentative '*'),
'BLAGN' / 'BLAGN (QSO)' -> lrd=0. broad_line=1 where a broad-line FWHM is measured; empty for the three
'BLAGN*' objects selected by SED shape only (no H-alpha coverage).

Usage: python ingest.py <dir containing src/sample631.tex>
"""
import csv
import re
import sys
from pathlib import Path

tex = (Path(sys.argv[1]) / "src" / "sample631.tex").read_text()
i0 = tex.index(r"\caption{Broad-line Emitter Sample}")
body = tex[tex.index(r"\startdata", i0) + len(r"\startdata"):tex.index(r"\enddata", i0)]
rows, nlrd = [], 0
for line in body.split(r"\\"):
    line = line.strip()
    if not line:
        continue
    c = [x.strip() for x in line.split("&")]
    assert len(c) == 12, c
    nid, ra, dec, z, m444, lbr, fbr, fwhm, lname, mbh, typ, flag = c
    assert re.fullmatch(r"NX\d+", nid) and re.fullmatch(r"\d+\.\d{6}", ra) and re.fullmatch(r"\d+\.\d{6}", dec)
    m = re.fullmatch(r"(BLAGN\*?)(?: \((LRD\*?|QSO)\))?", typ)
    assert m, typ
    lrd = "1" if (m.group(2) or "").startswith("LRD") else "0"
    nlrd += lrd == "1"
    bl = "" if fwhm == r"\nodata" else "1"
    mag = re.match(r"([0-9.]+) \\pm", m444).group(1)
    note = f"Type: {typ}; BLAGN selection flag {flag}"
    if bl:
        line_clean = lname.replace("$", "").replace(chr(92), "")
        fw = re.match(r"(\d+)", fwhm).group(1)
        note += f"; broad {line_clean} FWHM {fw} km/s"
    rows.append([nid, ra, dec, z, "grism", "NEXUS", lrd, "NIRCam/grism", bl, mag, note])
assert len(rows) == 23 and nlrd == 15, (len(rows), nlrd)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows, {nlrd} LRDs)")
