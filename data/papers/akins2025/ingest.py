"""Build objects.csv for Akins et al. 2025, ApJ 991, 37 (arXiv:2406.10341), COSMOS-Web LRDs.

Raw files:
  journal/apjade984t1_mrt.txt  journal machine-readable Table 1 (434 LRDs)
      https://content.cld.iop.org/journals/0004-637X/991/1/37/revision2/apjade984t1_mrt.txt
  arxiv_src/cosmosweb_LRD_overview_paper.tex  arXiv LaTeX source (https://arxiv.org/e-print/2406.10341),
      used only for the table "Spectroscopic measurements for COS-756434" (z_spec, RA, Dec, broad-line FWHM).
Optional cross-check (used only if present):
  github/COSMOS-Web_LRDs.dat  https://github.com/hollisakins/akins24_cw (commit 9fde3b9baf10cc110e83bbfb84ec5da476dc9e8c)

Usage: python ingest.py <raw dir containing journal/ and arxiv_src/>
"""
import csv
import re
import sys
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy.io import ascii
import astropy.units as u

raw = Path(sys.argv[1])
t = ascii.read(raw / "journal" / "apjade984t1_mrt.txt", format="cds")
assert len(t) == 434, len(t)
assert len(set(int(x) for x in t["ID"])) == 434

# Spectroscopic table for COS-756434 (the paper adopts its z_spec)
tex = (raw / "arxiv_src" / "cosmosweb_LRD_overview_paper.tex").read_text()
blk = tex[tex.index(r"\label{tab:spec}"):]
blk = blk[:blk.index(r"\enddata")]
zspec = re.search(r"\$z_\{\\rm spec\}\$ & \\dots & ([0-9.]+)\\pm", blk).group(1)
ra_s = re.search(r"R\.A\. & hms & ([0-9]+)\\mathrm\{:\}([0-9]+)\\mathrm\{:\}([0-9.]+)", blk).groups()
de_s = re.search(r"Decl\. & dms & ([+-][0-9]+)\\mathrm\{:\}([0-9]+)\\mathrm\{:\}([0-9.]+)", blk).groups()
fwhm_broad = re.search(r"FWHM\$_\{\\rm broad\}\$ & km\\,s\$\^\{-1\}\$ & ([0-9]+)", blk).group(1)
spec_c = SkyCoord(":".join(ra_s), ":".join(de_s), unit=(u.hourangle, u.deg))
SPEC_ID = 756434
row = t[t["ID"] == SPEC_ID][0]
sep = spec_c.separation(SkyCoord(row["RAdeg"] * u.deg, row["DEdeg"] * u.deg)).arcsec
assert sep < 0.3, sep
assert float(zspec) == 6.9993 and int(fwhm_broad) > 1000

gh_file = raw / "github" / "COSMOS-Web_LRDs.dat"
if gh_file.exists():
    from astropy.table import Table
    g = {int(x["id"]): x for x in Table.read(gh_file, format="ascii.ecsv")}
    assert set(g) == set(int(x) for x in t["ID"])
    for r in t:
        y = g[int(r["ID"])]
        assert abs(y["ra"] - r["RAdeg"]) < 1.5e-6 and abs(y["dec"] - r["DEdeg"]) < 1.5e-6, r["ID"]
        assert abs(y["z_qso_med"] - r["zQSO"]) < 0.0051, r["ID"]

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "spec", "broad_line", "f444w", "notes"])
    for r in t:
        i = int(r["ID"])
        m444 = float(r["F444mag"])
        f444w = f"{m444:.2f}" if m444 > 0 else ""  # -99 = null in the MRT
        zgal = f"z_gal={float(r['zGal']):.2f}" if float(r["zGal"]) > 0 else ""
        if i == SPEC_ID:
            w.writerow([f"COS-{i}", f"{r['RAdeg']:.6f}", f"{r['DEdeg']:.6f}", zspec, "spec", "COSMOS",
                        "NIRSpec/PRISM", "1", f444w,
                        f"z_spec from paper's spectroscopic table; broad FWHM {fwhm_broad} km/s; "
                        f"z_qso={float(r['zQSO']):.2f}; {zgal}"])
        else:
            w.writerow([f"COS-{i}", f"{r['RAdeg']:.6f}", f"{r['DEdeg']:.6f}", f"{float(r['zQSO']):.2f}", "phot",
                        "COSMOS", "", "", f444w, zgal])
print(f"wrote {out} ({len(t)} rows; COS-{SPEC_ID} z_spec={zspec}, sep={sep:.3f} arcsec)")
