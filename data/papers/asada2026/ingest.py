"""Build objects.csv for Asada et al. 2026 (accepted in ApJL; arXiv:2601.10573),
"Origins of the UV continuum and Balmer emission lines in Little Red Dots: observational
validation of dense gas envelope models enshrouding the AGN"
(Asada, Y., Inayoshi, K., Fei, Q., Fujimoto, S., Willott, C.).

Raw files:
  eprint.tgz   arXiv LaTeX source, v4 (accepted version)
               https://arxiv.org/e-print/2601.10573
               SHA-256 e34d89aa3a7bad1d9044ad5fabc59d3570289de7fd9b4dd51a2b301139d863fb
               Appendix table "LRDs and LBDs used in this work" (tab:sample_lrds) in sample701.tex:
               27 LRDs and 7 "little blue dots" (LBDs, the control sample), with DJA root,
               program ID, DJA source ID, RA/Dec (deg) and z_spec.

Section 2: all 34 are broad-Halpha emitters (chi2 ratio > 1.6) in DJA v4.4 NIRSpec/PRISM spectra at
5 < z < 7.2; LRDs have V-shaped continua (lrd=1); LBDs are compact broad-line AGN without the
V shape (lrd=0). The paper gives no X-ray or variability result per object.

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "eprint.tgz") as tf:
    tex = tf.extractfile("sample701.tex").read().decode("utf-8")
# sample sizes stated in the text (Section 2)
assert "We obtain a sample of 27 LRDs in total" in tex
assert "We obtain a sample of 7 LBDs" in tex

seg = tex[tex.index(r"\label{tab:sample_lrds}"):]
seg = seg[seg.index(r"\startdata"):seg.index(r"\enddata")]

# DJA root prefix -> field (the root names encode the survey/field of the MSA mask)
FIELD = [("capers-cos", "COSMOS"), ("cosmos-", "COSMOS"), ("rubies-egs", "EGS"), ("capers-egs", "EGS"),
         ("ceers", "EGS"), ("rubies-uds", "UDS"), ("gto-wide-uds", "UDS"), ("jades-gds", "GOODS-S"),
         ("gds-", "GOODS-S"), ("jades-gdn", "GOODS-N"), ("uncover", "Abell 2744"),
         ("macs1149", "MACS J1149"), ("macs1423", "MACS J1423"), ("macsj0647", "MACS J0647"),
         ("abell370", "Abell 370"), ("nexus", "NEP")]

rows, group = [], None
for line in seg.splitlines():
    line = re.sub(r"(?<!\\)%.*", "", line).strip()
    if "multicolumn" in line:
        group = re.search(r"\{(LRDs|LBDs)\}", line).group(1)
        continue
    line = line.replace(r"\hline", "").replace(r"\startdata", "").strip()
    if not line:
        continue
    c = [x.strip() for x in line.rstrip("\\").split("&")]
    assert len(c) == 9, c
    root, pid, srcid, ra, dec = c[0], int(c[1]), int(c[2]), c[3], c[4]
    z = re.match(r"\$([0-9.]+)_", c[5]).group(1)
    assert re.fullmatch(r"\d+\.\d{6}", ra) and re.fullmatch(r"-?\d+\.\d{6}", dec), (ra, dec)
    field = next(f for p, f in FIELD if root.startswith(p))
    lrd = {"LRDs": "1", "LBDs": "0"}[group]
    notes = f"DJA {root} srcid {srcid}; PID {pid}" + ("" if lrd == "1" else "; LBD (control sample, not V-shaped)")
    rows.append([f"{root}-{srcid}", ra, dec, z, "spec", field, lrd, "NIRSpec/PRISM", "1", notes])

assert sum(r[6] == "1" for r in rows) == 27 and sum(r[6] == "0" for r in rows) == 7, len(rows)
assert len(rows) == 34
assert len({r[0] for r in rows}) == len(rows)
assert all(5 < float(r[3]) < 7.2 for r in rows)

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows: 27 LRDs, 7 LBDs)")
