"""Build objects.csv for Taylor et al. 2026, "Little Red Dots with Broad Hbeta Lines Reveal the Black Hole
Mass Function at 7<z<9.5" (A. J. Taylor, S. L. Finkelstein, H. B. Akins, V. Kokorev, et al.;
arXiv:2610.37564v1, submitted to ApJ).

Raw file:
  arxiv_2610.37564.src   arXiv LaTeX source, v1 (tar.gz), https://arxiv.org/e-print/2610.37564
                         SHA-256 aac82d27f7d72bf23fbe468511d8b9525e2d010054ac200a140e8c6a6e6f144e
    main.tex, Table "Measured Properties of BLAGN at 7<z<9.5" (tab:sample): Source ID, R.A., Decl. [deg],
      z_spec -> id, ra, dec, z
    main.tex, Table "Spectra Contributing to the BLAGN Sample" (tab:apdx): same 20 objects with Field,
      Reference and Spectra -> field, notes; also used to cross-check id/ra/dec/z of tab:sample

Paper statements used for the per-row flags:
  - Abstract / Sect. "LRD Selection" (sec:lrdselect): "our 20 object sample consists entirely of LRDs" -> lrd=1
  - every object has a statistically significant broad-Hbeta component in its NIRSpec PRISM spectrum
    (Sect. "Broad-line Fitting and Statistical Testing") -> broad_line=1, spec=NIRSpec/PRISM
  - z_spec from NIRSpec PRISM -> z_type=spec
No X-ray or variability results are given, so xray/variable are left empty.

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

N_PAPER = 20  # abstract: "We find a sample of 20 sources with statistically significant broad-Hbeta emission"

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2610.37564.src") as tf:
    tex = tf.extractfile("main.tex").read().decode("utf-8")
assert "We find a sample of 20 sources with statistically significant broad-\\Hb{} emission" in tex
assert "our 20 object sample consists entirely of LRDs" in tex


def table_rows(label):
    seg = tex[tex.index(r"\label{" + label + "}"):]
    seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
    rows = []
    for line in seg.split(r"\\"):
        line = re.sub(r"(?<!\\)%.*", "", line).strip()
        if line:
            rows.append([c.strip() for c in line.split("&")])
    return rows, tex[tex.index(r"\label{" + label + "}"):].split(r"\end{deluxetable", 1)[0]


def jname(s):
    return s.replace("--", "-")  # tab:apdx typesets the minus as an en dash


sample, _ = table_rows("tab:sample")
apdx, apdx_block = table_rows("tab:apdx")
assert len(sample) == N_PAPER, len(sample)
assert len(apdx) == N_PAPER, len(apdx)
assert all(len(r) == 11 for r in sample), [len(r) for r in sample]
assert all(len(r) == 8 for r in apdx), [len(r) for r in apdx]

ids = [r[0] for r in sample]
assert len(set(ids)) == N_PAPER, "duplicate ids"
assert all(re.fullmatch(r"J\d{6}\.\d{2}[+-]\d{6}\.\d", i) for i in ids), ids

# reference numbers in tab:apdx -> citation keys, from its \tablecomments
refkeys = dict(re.findall(r"\[(\d+)\] \\cite\{(\w+)\}", apdx_block))
assert len(refkeys) == 8, refkeys
LABEL = {"greene24": "Greene+24", "furtak24": "Furtak+24", "lin26": "Lin+26", "naidu25": "Naidu+25",
         "wang24b": "Wang+24", "kokorev23": "Kokorev+23", "tripodi25": "Tripodi+25", "taylor25c": "Taylor+25"}
assert set(refkeys.values()) == set(LABEL), refkeys

ap = {jname(r[0]): r for r in apdx}
assert set(ap) == set(ids), set(ap) ^ set(ids)

# Sect. "LRD Selection": two objects fail the beta_opt>0 cut but are still classified as LRDs
SECT_NOTE = {
    "J114933.82+222059.2": "beta_opt slightly <0 but classified as LRD (Sect. LRD Selection)",
    "J021718.46-051326.2": "superposed with a blue lower-z interloper; classified as LRD (Sect. LRD Selection)",
}
for k in SECT_NOTE:
    assert k in tex and k in ids, k

rows = []
for r in sample:
    sid, ra, dec, z = r[0], r[1], r[2], r[3]
    a = ap[sid]
    # cross-check the two tables of the same paper
    assert (a[1], a[2], a[3]) == (ra, dec, z), (sid, a[1:4], (ra, dec, z))
    assert len(ra.split(".")[1]) >= 6 and len(dec.split(".")[1]) >= 6, (sid, ra, dec)
    ra_f, dec_f, z_f = float(ra), float(dec), float(z)
    assert 0 <= ra_f < 360 and -90 <= dec_f <= 90
    assert 7.0 < z_f < 9.5, (sid, z)
    # the J-name (truncated sexagesimal) must agree with the decimal position to < 0.15"
    j = sid[1:]
    jc = SkyCoord(f"{j[:2]}h{j[2:4]}m{j[4:9]}s", f"{j[9:12]}d{j[12:14]}m{j[14:]}s")
    sep = jc.separation(SkyCoord(ra_f * u.deg, dec_f * u.deg)).arcsec
    assert sep < 0.15, (sid, sep)
    refs = a[6]
    if refs == "New":
        ref_txt = "new in this paper"
    else:
        nums = re.fullmatch(r"\[([\d,]+)\]", refs).group(1).split(",")
        ref_txt = "previously in " + ", ".join(LABEL[refkeys[n]] for n in nums)
    notes = f"{ref_txt}; spectra {a[7]}"
    if sid in SECT_NOTE:
        notes += "; " + SECT_NOTE[sid]
    rows.append([sid, ra, dec, z, "spec", a[5], "1", "NIRSpec/PRISM", "1", notes])

n_new = sum(1 for r in apdx if r[6] == "New")
assert n_new == 13, n_new  # abstract: "including 13 new sources"

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows, {n_new} new in the paper, z {min(float(r[3]) for r in rows)}-"
      f"{max(float(r[3]) for r in rows)})")
