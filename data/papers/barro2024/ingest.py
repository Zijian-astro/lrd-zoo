"""Build objects.csv for Barro et al. 2024, ApJ 963, 128 (arXiv:2305.14418), extremely red objects (EROs) in CEERS.

Raw file: arXiv LaTeX source (https://arxiv.org/e-print/2305.14418, v1, the only arXiv version), extracted to
  <dir>/arxiv_src/. No VizieR catalogue or journal MRT exists. Two tables together list all 37 EROs:
    ms.tex      Table 1 "MIRI and NIRSpec EROs at 5<z<9" (label tab:objects, 8 rows: ID, RA, Dec, z_phot, z_spec, masses)
    table2.tex  Table "remaining 29 EROs" (label tab:otherobjects, 29 rows: ID, RA, Dec, z_phot, masses)

Usage: python ingest.py <raw dir containing arxiv_src/ms.tex and arxiv_src/table2.tex>
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

src = Path(sys.argv[1]) / "arxiv_src"


def table_rows(tex, label):
    blk = tex[tex.index(r"\label{" + label + "}"):]
    blk = blk[:blk.index(r"\end{tabular}")]
    body = blk.split(r"\hline")  # [preamble, '', header, data rows, ...] for \hline\hline header \hline rows \hline\hline
    assert "ID" in body[2] and "R.A." in body[2], body[2]
    rows = []
    for line in "\n".join(body[3:]).splitlines():
        line = line.strip()
        if not line or line.startswith("%") or "&" not in line:
            continue
        rows.append([x.strip() for x in line.rstrip("\\").split("&")])
    return rows


def split_id(cell):
    m = re.fullmatch(r"([A-Za-z0-9-]+)\s*(\$\^\{(.*)\}\$)?", cell)
    assert m, cell
    return m.group(1), (m.group(3) or "").replace(" ", "")


def central(cell):
    m = re.match(r"\$?\s*([0-9.]+)\s*\$?\^", cell)
    assert m, cell
    return m.group(1)


FOOT1 = {"\\dagger": "also in Akins et al. 2023", "\\dagger\\dagger": "also in Kocevski et al. 2023 as MPTID-746",
         "\\dagger\\dagger\\dagger": "also in Fujimoto et al. 2023 as MPTID-20"}

out_rows = []
t1 = table_rows((src / "ms.tex").read_text(), "tab:objects")
assert len(t1) == 8, len(t1)
for p in t1:
    oid, mark = split_id(p[0])
    zphot = central(p[3])
    zspec = p[4].strip("$ ")
    notes = ["Table 1 (MIRI/NIRSpec subsample)"]
    if mark:
        notes.append(FOOT1[mark])
    if zspec != "---":
        float(zspec)
        notes.append(f"z_phot={zphot}")
        out_rows.append([oid, p[1], p[2], zspec, "spec", "EGS", "NIRSpec", notes])
    else:
        out_rows.append([oid, p[1], p[2], zphot, "phot", "EGS", "", notes])

t2 = table_rows((src / "table2.tex").read_text(), "tab:otherobjects")
assert len(t2) == 29, len(t2)
for p in t2:
    oid, mark = split_id(p[0])
    marks = mark.replace(",", "")
    notes = ["Table 2 (remaining EROs)"]
    if "\\dagger" in marks:
        notes.append("also in Labbé et al. 2023")
    if "\\star" in marks:
        notes.append("also in Pérez-González et al. 2023")
    assert marks.replace("\\dagger", "").replace("\\star", "") == "", mark
    out_rows.append([oid, p[1], p[2], central(p[3]), "phot", "EGS", "", notes])

assert len(out_rows) == 37
assert len({r[0] for r in out_rows}) == 37
for r in out_rows:
    float(r[1]), float(r[2])
# flag rows whose published coordinates are identical to another row's (a typo in the paper's table)
pos = Counter((float(r[1]), float(r[2])) for r in out_rows)
for r in out_rows:
    if pos[(float(r[1]), float(r[2]))] > 1:
        others = [x[0] for x in out_rows if x is not r and (float(x[1]), float(x[2])) == (float(r[1]), float(r[2]))]
        r[7].append(f"published RA/Dec identical to {', '.join(others)} (likely a typo in the paper's table)")

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "spec", "notes"])
    for r in out_rows:
        w.writerow(r[:7] + ["; ".join(r[7])])
print(f"wrote {out} ({len(out_rows)} rows, {sum(r[4] == 'spec' for r in out_rows)} spec-z)")
