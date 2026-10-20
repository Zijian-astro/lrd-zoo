"""Build objects.csv for Maiolino et al. 2024 (JADES: the diverse population of infant black holes at 4<z<11).

Raw file: arXiv LaTeX source of 2308.01230 (https://arxiv.org/e-print/2308.01230, v4 = accepted version), saved as
  arxiv_2308.01230.tar.gz   (member Infant_BH_revised_clean2.tex is read directly from the tarball)

Tables used (coordinates are encoded in the "JADES Name", JADES-GS+RA+Dec / JADES-GN+RA+Dec, decimal degrees):
  tab:measures       9 broad-line AGN needing one broad Halpha component (footnote d = "tentative" BLR, DeltaBIC<10)
  tab:measures_dual  3 AGN needing two broad Halpha components (candidate merging/dual BHs)
GN-z11 (also in the inferred-properties table) has no coordinates in this paper and is not included.

Usage: python ingest.py <dir containing arxiv_2308.01230.tar.gz>
"""
import csv
import re
import sys
import tarfile
from pathlib import Path

raw = Path(sys.argv[1])
with tarfile.open(raw / "arxiv_2308.01230.tar.gz") as tf:
    tex = tf.extractfile("Infant_BH_revised_clean2.tex").read().decode("utf-8")


def table_body(label):
    i = tex.index(r"\label{" + label + "}")
    beg = tex.rindex(r"\begin{tabular}", 0, i)
    body = tex[beg:tex.index(r"\end{tabular}", beg)]
    return body.split(r"\hline")[2]            # [0] preamble, [1] header, [2] data, [3] closing


NAME = re.compile(r"JADES-G([SN])([+-]\d+\.\d+)([+-]\d+\.\d+)")
rows = []
for label, kind in (("tab:measures", "single"), ("tab:measures_dual", "dual")):
    for line in table_body(label).split(r"\\"):
        line = line.strip()
        m = NAME.search(line)
        if not m:
            continue                           # second (BLR2) line of a dual entry
        cells = [c.strip() for c in line.split("&")]
        nid = re.sub(r"\\multirow\{2\}\{\*\}\{(.*)\}", r"\1", cells[0])
        z = re.sub(r"\\multirow\{2\}\{\*\}\{(.*)\}", r"\1", cells[2])
        tentative = "$^d$" in nid
        nid = nid.replace("$^d$", "").strip()
        assert re.fullmatch(r"\d+", nid) and float(z) > 4, (nid, z)
        rows.append(dict(nid=nid, name=m.group(0), field="GOODS-S" if m.group(1) == "S" else "GOODS-N",
                         ra=m.group(2).lstrip("+"), dec=m.group(3).lstrip("+"), z=z, kind=kind, tentative=tentative))

assert len(rows) == 12 and len({r["nid"] for r in rows}) == 12, len(rows)
assert sum(r["tentative"] for r in rows) == 2 and sum(r["kind"] == "dual" for r in rows) == 3

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "spec", "broad_line", "notes"])
    for r in rows:
        float(r["ra"]), float(r["dec"])
        notes = [f"NIRSpec ID {r['nid']}"]
        if r["tentative"]:
            notes.append("tentative BLR detection (DeltaBIC<10)")
        if r["kind"] == "dual":
            notes.append("two broad Halpha components (candidate dual/merging BH)")
        w.writerow([r["name"], r["ra"], r["dec"], r["z"], "spec", r["field"], "", "NIRSpec/grating", "1",
                    "; ".join(notes)])
print(f"wrote {out} ({len(rows)} rows)")
