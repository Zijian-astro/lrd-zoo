"""Build objects.csv for Zhang, C., Zhang, H. & Wu, Q. 2026 (arXiv:2611.06026, preprint),
"Spectroscopy-informed Deep Learning Searches for Photometric Little Red Dots in JWST Surveys".

Raw file:
  arxiv_2611.06026.src   arXiv LaTeX source of v1 (tar.gz), https://arxiv.org/e-print/2611.06026
                         SHA-256 feca5541aa0e7684e1467c73d5f05fa05dc42e48d70ef0337fb960fd8c47d4ee
                         (top-level file main_v3.tex)

Tables used (all complete in the LaTeX source):
  tab:fp_recovery        35 spectroscopic LRD candidates (DJA NIRSpec/PRISM spectra, z_spec)
  tab:fp_grating_halpha  BIC-selected Halpha model for 13 of them with grating coverage
                         (broad_line flag; z cross-checked against tab:fp_recovery)
  tab:sapphires          5 SAPPHIRES (MACS J0416) candidates
  tab:beacon_candidates  18 BEACON DR1 candidates (z_phot)
Not used: tab:dja_candidates, a 10-row excerpt of the 357 DJA candidates whose full table is
"published in its entirety in machine-readable format" (not available while the paper is a preprint).

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2611.06026.src") as tf:
    tex = tf.extractfile("main_v3.tex").read().decode("utf-8")

# numbers the paper states in the text
assert "yields 35 candidates at $p \\geq 0.80$" in tex
assert "yields five LRD candidates" in tex
assert "Of these, 18 are assigned probabilities exceeding $p=0.80$" in tex
assert "The preferred model includes a broad H$\\alpha$ component for 10 sources" in tex


def table(label):
    seg = tex[tex.index(r"\label{" + label + "}"):]
    seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
    out = []
    for row in seg.split(r"\\"):
        row = re.sub(r"(?<!\\)%.*", "", row).strip()
        if not row:
            continue
        out.append([x.strip() for x in row.split("&")])
    return out


def num(s):
    s = s.replace("$", "").strip()
    return "" if s in (r"\cdots", r"\nodata", "") else s


# --- Halpha grating fits: '#', ID, z, dBIC, Model, FWHM
grat = {}
for c in table("tab:fp_grating_halpha"):
    assert len(c) == 6, c
    grat[c[1]] = dict(n=int(c[0]), z=float(c[2]), model=c[4])
assert len(grat) == 13, len(grat)
assert sum(g["model"] == "Broad" for g in grat.values()) == 10
assert {g["model"] for g in grat.values()} == {"Broad", "Narrow", "No emission"}

FIELD = [  # DJA spectrum root prefix -> field
    ("rubies-uds", "UDS"), ("rubies-egs", "EGS"), ("ceers", "EGS"), ("capers-cos", "COSMOS"),
    ("nexus", "NEP"), ("jades-gds", "GOODS-S"), ("gds-", "GOODS-S"), ("macs0416", "MACS J0416"),
    ("macs0417", "MACS J0417"), ("macs1149", "MACS J1149"), ("abell370", "Abell 370"),
]

HEAD = ["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w", "notes"]
rows = []

# --- spectroscopic candidates: #, ID, RA, Dec, z_spec, p, mF444W, bUV, bopt, B, C
spec = table("tab:fp_recovery")
assert len(spec) == 35, len(spec)
for c in spec:
    assert len(c) == 11, c
    n, sid, ra, dec, z, p, m = int(c[0]), c[1], num(c[2]), num(c[3]), num(c[4]), num(c[5]), num(c[6])
    field = next(f for pre, f in FIELD if sid.startswith(pre))
    g = grat.get(sid)
    if g:
        assert g["n"] == n, (sid, g, n)
        dz = abs(g["z"] - float(z))
        assert dz <= 0.02, (sid, g["z"], z)
        if dz > 0.0051:  # tab:fp_recovery gives z to 2 decimals; more than rounding apart
            print(f"WARNING: {sid}: z={z} (tab:fp_recovery) vs {g['z']} (tab:fp_grating_halpha)")
        bl = "1" if g["model"] == "Broad" else "0"
        sp = "NIRSpec"
        note = f"spectroscopic candidate #{n}, p_LRD={p}; PRISM + grating, Halpha model: {g['model']} (Table tab:fp_grating_halpha)"
    else:
        bl, sp = "", "NIRSpec/PRISM"
        note = f"spectroscopic candidate #{n}, p_LRD={p}; DJA PRISM spectrum"
    rows.append([sid, ra, dec, z, "spec", field, "1", sp, bl, m, note + "; labelled non-LRD in the paper's training set (Sect. 'Spectroscopic LRD Candidates')"])
assert sum(1 for c in spec if c[1] in grat) == 13

# --- SAPPHIRES: #, ID, RA, Dec, z, p, bUV, bopt, F150W-F200W, F277W-F444W, mF444W
sap = table("tab:sapphires")
assert len(sap) == 5, len(sap)
for c in sap:
    assert len(c) == 11, c
    note = f"SAPPHIRES EDR candidate #{c[0]}, p={num(c[5])}; z type not stated in the paper"
    if c[1] == "8760":
        assert "matches the previously reported LRD candidate ID-8760" in tex
        note += "; = ID-8760 of Fudamoto et al. 2025"
    rows.append([f"SAPPHIRES-{c[1]}", num(c[2]), num(c[3]), num(c[4]), "", "MACS J0416", "1", "", "",
                 num(c[10]), note])

# --- BEACON: #, ID, RA, Dec, z_phot, p, bUV, bopt, F115W-F200W, F277W-F444W, mF444W
bea = table("tab:beacon_candidates")
assert len(bea) == 18, len(bea)
for c in bea:
    assert len(c) == 11, c
    bid = c[1].replace(r"\_", "_")
    m = re.fullmatch(r"beacon_(\d{4}[pm-]\d{4})-(\d+)", bid)
    assert m, bid
    note = f"BEACON DR1 candidate #{c[0]}, p={num(c[5])}"
    if bid == "beacon_0014-3025-6766":
        assert "BEACON 0014-3025-6766 is the LRD uncover-61-v4-27114" in tex
        note += "; = uncover-61-v4-27114 (Barro et al. 2026)"
    rows.append([bid, num(c[2]), num(c[3]), num(c[4]), "phot", f"BEACON {m.group(1)}", "1", "", "",
                 num(c[10]), note])

assert len(rows) == 58
ids = [r[0] for r in rows]
assert len(set(ids)) == len(ids), "duplicate ids"
for r in rows:
    float(r[1]), float(r[2])

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(HEAD)
    w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows: 35 spectroscopic, 5 SAPPHIRES, 18 BEACON)")
