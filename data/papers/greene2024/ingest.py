"""Build objects.csv for Greene et al. 2024 (UNCOVER spectroscopy of compact red sources / LRDs).

Raw file: arXiv LaTeX source of 2309.05714 (https://arxiv.org/e-print/2309.05714, v1), saved as
  arxiv_2309.05714.tar.gz   (member paper.tex is read directly from the tarball)

Tables used:
  table:thesample  "Sample"     17 NIRSpec/PRISM targets (MSAID, RA, Dec in decimal degrees, z_spec, mu, F444W, ...)
  table:thefits    "Halpha fits" -- per the table comment, only definite broad-line objects have L_Halpha listed;
                   rows without L_Halpha are the paper's "unconfirmed" broad-line AGN.
Rows with z_spec = 0.00 and no magnification are the three brown dwarfs (Burgasser+2023) named in the text.
Rows with footnote a are the three images of the triply-lensed A2744-QSO1 (13123 is the coadded spectrum in the fits table).

Usage: python ingest.py <dir containing arxiv_2309.05714.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2309.05714.tar.gz") as tf:
    tex = tf.extractfile("paper.tex").read().decode("utf-8")


def table_rows(label):
    """Data rows (lists of cells) of the deluxetable carrying \\label{<label>}."""
    i = tex.index(r"\label{" + label + "}")
    start = tex.index(r"\startdata", i) + len(r"\startdata")
    body = tex[start:tex.index(r"\enddata", start)]
    rows = []
    for line in body.split(r"\\"):
        line = re.sub(r"(?m)%.*$", "", line).strip()
        if line:
            rows.append([c.strip() for c in line.split("&")])
    return rows


def msaid(cell):
    m = re.fullmatch(r"(\d+)(\$\^[ab]\$)?", cell.replace(" ", ""))
    assert m, cell
    return m.group(1), (m.group(2) or "").strip("$^")


sample = table_rows("table:thesample")
fits = table_rows("table:thefits")
assert len(sample) == 17, len(sample)

# broad-line status from the Halpha-fits table: column 7 (L_Halpha) is \nodata for "unconfirmed" objects
bl_status = {}
for r in fits:
    mid, _ = msaid(r[0])
    bl_status[mid] = "1" if r[6] != r"\nodata" else "0"
assert sum(v == "1" for v in bl_status.values()) == 9 and sum(v == "0" for v in bl_status.values()) == 3

out = Path(__file__).with_name("objects.csv")
n_bd = n_lrd = 0
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "f444w", "notes"])
    for r in sample:
        mid, foot = msaid(r[0])
        ra = r[1]
        dec = r[2].replace("$-$", "-")
        float(ra), float(dec)
        z = r[3].split("$")[0]
        mu = r[4]
        brown_dwarf = float(z) == 0.0 and mu == r"\nodata"
        notes = []
        if brown_dwarf:
            n_bd += 1
            lrd, bl = "0", ""
            notes.append("brown dwarf (z_spec=0.00 in table)")
        else:
            lrd = "1"
            n_lrd += 1
            if foot == "a":
                bl = bl_status["13123"]
                notes.append("one of three images of the triply-lensed A2744-QSO1 (13123/15383/16594)")
            else:
                bl = bl_status[mid]
            if bl == "0":
                notes.append("unconfirmed broad-line AGN")
            if mid == "35488":
                # Halpha table lists L_Halpha/M_BH (definite BL) but v1 text names 35488 as failing the chi2 cut
                notes.append("BL per Halpha-fits table; arXiv v1 text inconsistently lists 35488 as failing the chi2 cut")
        # brown dwarfs: leave z empty so they don't show up as z=0 extragalactic sources
        w.writerow([f"UNCOVER-{mid}", ra, dec, "" if brown_dwarf else z, "" if brown_dwarf else "spec", "Abell 2744",
                    lrd, "NIRSpec/PRISM", bl, r[7],
                    "; ".join(notes)])
assert n_bd == 3
print(f"wrote {out} ({len(sample)} rows, {n_lrd} lrd=1, {n_bd} brown dwarfs)")
