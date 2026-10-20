"""Build objects.csv for Zhang et al. 2025 (ApJ 985, 119; arXiv:2411.02729),
"Analysis of Multi-epoch JWST Images of ~300 Little Red Dots: Tentative Detection
of Variability in a Minority of Sources".

Raw files (all from https://github.com/Zijian-astro/variable_LRD_candidates and arXiv):
  unique_lrds_table.dat   parent sample of 906 compiled LRDs (ID, Ra, Dec, Field, ..., index)
  repo_tree.json          GitHub API listing of the repo (git/trees/HEAD?recursive=1); the
                          light-curve files all_LRDs/<FLD>/lc/lc_data/<index>_<band>_light_curve.txt
                          identify the 314 LRDs with multi-epoch detections (= variability tested)
  arxiv_2411.02729.src    arXiv LaTeX source (tar.gz); Table "LRDs that show variability of
                          SNR_var>3" (tab:vari_LRDs) gives the 8 variable candidates

Usage: python -I ingest.py <rawdir>
"""
import csv
import json
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

from astropy.io import ascii

raw = Path(sys.argv[1])
t = ascii.read(raw / "unique_lrds_table.dat", format="commented_header")
assert len(t) == 906, len(t)
assert len(set(t["index"])) == 906

# LID prefix used by the paper (Table 3 / repo file names) for the five variability fields
PREFIX = {"A2744": "A2744", "COSMOS": "COS", "GOODS-N": "GN", "GOODS-S": "GS", "UDS": "UDS"}
DIR2FIELD = {"A2744": "A2744", "COS": "COSMOS", "GN": "GOODS-N", "GS": "GOODS-S", "UDS": "UDS"}

# --- LRDs with multi-epoch light curves (variability tested) -------------------------------
tree = json.loads((raw / "repo_tree.json").read_text())
assert not tree.get("truncated")
tested = set()
for item in tree["tree"]:
    m = re.fullmatch(r"all_LRDs/([^/]+)/lc/lc_data/(\d+)_F\w+_light_curve\.txt", item["path"])
    if m:
        tested.add((DIR2FIELD[m.group(1)], int(m.group(2))))
assert len(tested) == 314, len(tested)
per_field = Counter(f for f, _ in tested)
# paper Table 1 ("With multi-epoch observations"): UDS 97, GOODS-S 70, GOODS-N 8, A2744 25, COSMOS 114
assert per_field == {"UDS": 97, "GOODS-S": 70, "GOODS-N": 8, "A2744": 25, "COSMOS": 114}, per_field

# --- variable candidates from the paper table -----------------------------------------------
with tarfile.open(raw / "arxiv_2411.02729.src") as tf:
    tex = tf.extractfile("ms.tex").read().decode("utf-8")
seg = tex[tex.index(r"\label{tab:vari_LRDs}"):]
seg = seg[seg.index(r"\startdata") + len(r"\startdata"):seg.index(r"\enddata")]
var = {}
for row in seg.split(r"\\"):
    row = row.replace(r"\hline", "").strip()
    if not row:
        continue
    c = [x.strip() for x in row.split("&")]
    m = re.fullmatch(r"\\textnormal\{(\w+)-\}(\d+)", c[0])
    lid = (m.group(1), int(m.group(2)))
    band = re.sub(r"\\textnormal\{(.*)\}", r"\1", c[13])
    var[lid] = dict(ra=float(c[1]), dec=float(c[2]), z=c[4], ztype=c[5], snr=c[9], dm=c[10], band=band)
assert len(var) == 8, var.keys()

rows = []
by_lid = {}
for r in t:
    field = str(r["Field"])
    idx = int(r["index"])
    pre = PREFIX.get(field, field)
    lid = f"{pre}-{idx}"
    zbest, zphot, zspec = float(r["zbest"]), float(r["zphot"]), float(r["zspec"])
    if zspec > 0 and abs(zbest - zspec) < 1e-3:
        ztype = "spec"
    elif abs(zbest - zphot) < 1e-3:
        ztype = "phot"
    else:
        ztype = ""
    z = f"{zbest:.4f}".rstrip("0").rstrip(".")
    notes = [f"orig. ID {r['ID']} ({r['ref']})"]
    if (field, idx) in tested:
        variable = "0"
    else:
        variable = ""
    key = (pre, idx)
    if key in var:
        v = var.pop(key)
        # same object as the paper table: coordinates agree to the 6 printed decimals
        assert abs(v["ra"] - float(r["Ra"])) < 2e-6 and abs(v["dec"] - float(r["Dec"])) < 2e-6, (lid, v, r)
        assert (field, idx) in tested
        variable = "1"
        ptype = {"1": "spec", "0": "phot"}[v["ztype"]]
        if abs(float(v["z"]) - zbest) > 1e-3 or ptype != ztype:
            notes.append(f"z from paper Table 3 (repo table: zbest={z})")
        z, ztype = v["z"], ptype
        notes.append(f"variable candidate: max SNR_var={v['snr']}, dm={v['dm']} mag in {v['band']}")
    if variable == "" and field in PREFIX:
        notes.append("no multi-epoch detection (not tested)")
    elif variable == "":
        notes.append("outside the five variability fields (not tested)")
    rows.append([lid, f"{float(r['Ra']):.7f}", f"{float(r['Dec']):.7f}", z, ztype, field, "1", variable,
                 "; ".join(notes)])
assert not var, var  # every paper-table candidate matched

out = Path(__file__).with_name("objects.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "ra", "dec", "z", "z_type", "field", "lrd", "variable", "notes"])
    w.writerows(rows)
nvar = sum(r[7] == "1" for r in rows)
ntest = sum(r[7] != "" for r in rows)
print(f"wrote {out} ({len(rows)} rows; {ntest} tested, {nvar} variable)")
