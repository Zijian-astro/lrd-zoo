"""Build objects.csv for Wang 2026 (arXiv:2611.24217), "A Tight Broad-line Width-Luminosity
Relation in Little Red Dots and Its Consequence for Virial Black Hole Masses" (H. Wang; preprint).

Raw files (arXiv v1 LaTeX source, https://arxiv.org/e-print/2611.24217,
SHA-256 ec2580a49784afccae0e41736cf15ad21cc6bbd6fa88a51aeb61ed503cc89c8e), extracted to <rawdir>/src/:
  src/tables/Table1_full.csv  Table 1 "The sample", full 44-row machine-readable version
      SHA-256 237e90d897c084aedc5284cb76a4fc84aea15b0cef8a2d2d6f27baba58f9d980
  src/tables/Table1_stub.tex  the five rows of Table 1 printed in the paper (cross-check only)
      SHA-256 75963a4d7de4a2579a12687661f02a62b6c4eb896a4544827e6cab164bd0f5a4
  src/numbers.tex             the paper's number macros (\\NLRD=29, \\NOther=15; cross-check only)
      SHA-256 48fa226f303a49b7326678cef8c5ae71a48403b00b7f301fc5f079109c7a1f39

Usage: python -I ingest.py <rawdir>
"""
import csv
import re
import sys
from pathlib import Path

raw = Path(sys.argv[1])
rows = list(csv.DictReader((raw / "src" / "tables" / "Table1_full.csv").open(newline="")))

# Sect. 2.3: "29 LRDs and 15 other broad-line sources" (macros \NLRD, \NOther); Table 1 note: 44 sources
macros = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", (raw / "src" / "numbers.tex").read_text()))
n_lrd, n_oth = int(macros["NLRD"]), int(macros["NOther"])
assert (n_lrd, n_oth) == (29, 15), (n_lrd, n_oth)
assert len(rows) == 44 == n_lrd + n_oth, len(rows)
assert sum(r["cls"] == "LRD" for r in rows) == n_lrd
assert sum(r["cls"] == "other" for r in rows) == n_oth
ids = [r["name"] for r in rows]
assert len(set(ids)) == len(ids), "duplicate ids"

# Cross-check: the five rows printed in the paper (RA/Dec to 5 decimals, z to 3) agree with the CSV
by_id = {r["name"]: r for r in rows}
stub = (raw / "src" / "tables" / "Table1_stub.tex").read_text()
body = stub.split(r"\startdata")[1].split(r"\enddata")[0]
n_stub = 0
for line in body.strip().split(r"\\"):
    if not line.strip():
        continue
    c = [x.strip().strip("$") for x in line.split("&")]
    r = by_id[c[0]]
    assert c[1] == r["cls"], c[0]
    assert abs(float(c[2]) - float(r["ra"])) < 6e-6 and abs(float(c[3]) - float(r["dec"])) < 6e-6, c[0]
    assert abs(float(c[4]) - float(r["z"])) < 6e-4, c[0]
    if (c[5], c[6]) != (r["program"], r["grating"]):
        print(f"WARNING: {c[0]} program/grating printed {c[5]}/{c[6]}, CSV {r['program']}/{r['grating']}")
    n_stub += 1
assert n_stub == 5, n_stub

# Sect. 2.3: all sources are in EGS or UDS; assign by position and check against the id prefix
def field(r):
    ra, dec = float(r["ra"]), float(r["dec"])
    if 214.0 < ra < 215.5 and 52.0 < dec < 53.5:
        f = "EGS"
    elif 34.0 < ra < 34.8 and -5.5 < dec < -4.9:
        f = "UDS"
    else:
        raise AssertionError(f"{r['name']} outside EGS/UDS")
    pre = r["name"].split("-")[0] if not r["name"].startswith("RUBIES") else "-".join(r["name"].split("-")[:2])
    assert {"RUBIES-UDS": "UDS", "RUBIES-EGS": "EGS", "CEERS": "EGS", "Skyfire": "EGS"}[pre] == f, r["name"]
    return f

LRD = {"LRD": "1", "other": "0"}
REF = {"T25": "Taylor+25", "K26": "Kocevski+26", "H25": "Hviding+25"}
out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    for r in rows:
        notes = (f"class {r['cls']} from {REF[r['label_ref']]}; Halpha broad FWHM {r['fwhm']}+-{r['fwhm_err']} km/s, "
                 f"log L(Halpha,broad) {r['logL']}; PID {r['program']} {r['grating']}; DJA {r['file']}")
        if r["absorption"] == "Y":
            notes += "; Halpha absorption fitted"
        w.writerow([r["name"], f"{float(r['ra']):.6f}", f"{float(r['dec']):.6f}", r["z"], "spec", field(r),
                    LRD[r["cls"]], "NIRSpec/grating", "1", notes])
print(f"wrote {out} ({len(rows)} rows: {n_lrd} LRDs, {n_oth} other broad-line sources)")
