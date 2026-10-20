#!/usr/bin/env python3
"""Merge every paper in data/papers/ into one de-duplicated LRD Zoo catalogue.

Rows from different papers that lie within --radius arcsec of each other are
grouped (friends-of-friends) into one object. Each object keeps a stable Zoo
name (LRDZ Jhhmmss.ss+ddmmss.s) through data/zoo_ids.json: once a name has
been minted it is reused on later builds even if new papers shift the mean
position slightly.

Outputs (data/build/):
  lrdzoo.json          everything the web page needs
  lrdzoo_objects.csv   one row per unique object
  lrdzoo_entries.csv   one row per (paper, object) entry, with the Zoo name
  references.bib       BibTeX for every included paper

Usage: python scripts/build_catalog.py [--radius 0.5]
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np
import yaml
from astropy import units as u
from astropy.coordinates import SkyCoord, search_around_sky

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import check_paper  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "data" / "papers"
BUILD = ROOT / "data" / "build"
ID_REGISTRY = ROOT / "data" / "zoo_ids.json"
CORRECTIONS = ROOT / "data" / "corrections.yaml"

# Deep fields, so that every paper's objects get the same field label.
# (name, RA, Dec, radius in deg)
FIELDS = [
    ("EGS", 214.90, 52.88, 0.6),
    ("GOODS-S", 53.13, -27.80, 0.45),
    ("GOODS-N", 189.22, 62.24, 0.45),
    ("UDS", 34.38, -5.18, 0.6),
    ("COSMOS", 150.12, 2.20, 1.3),
    ("Abell 2744", 3.55, -30.38, 0.35),
    ("Abell 370", 39.97, -1.58, 0.25),
    ("MACS J0416", 64.04, -24.07, 0.25),
    ("MACS J0417", 64.39, -11.91, 0.25),
    ("MACS J1149", 177.40, 22.40, 0.25),
    ("MACS J1423", 215.95, 24.08, 0.25),
    ("Abell S1063", 342.18, -44.53, 0.25),
    ("SMACS 0723", 110.83, -73.45, 0.25),
    ("El Gordo", 15.72, -49.25, 0.25),
    ("NEP-TDF", 260.70, 65.80, 0.4),
]
Z_RANK = {"spec": 0, "grism": 1, "phot": 2, "": 3}


def load_papers():
    papers, entries = [], []
    for folder in sorted(p for p in PAPERS.iterdir() if p.is_dir()):
        errs, _ = check_paper(folder)
        if errs:
            print(f"skipping {folder.name}: {len(errs)} validation error(s); run scripts/validate.py {folder.name}")
            continue
        meta = yaml.safe_load((folder / "meta.yaml").read_text())
        meta["sample_is_lrd"] = meta.get("sample_is_lrd", True)
        meta["facility"] = meta.get("facility", "JWST")
        with (folder / "objects.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            lrd = r.get("lrd", "")
            is_lrd = lrd == "1" or (meta["sample_is_lrd"] and lrd != "0")
            entries.append({
                "paper": meta["key"],
                "year": int(meta["year"]),
                "id": r["id"],
                "ra": float(r["ra"]),
                "dec": float(r["dec"]),
                "z": float(r["z"]) if r.get("z") else None,
                "z_type": r.get("z_type", "") or (meta.get("z_type", "") if r.get("z") else ""),
                "field": r.get("field", ""),
                "lrd": is_lrd,
                "lrd_flag": lrd,
                "spec": r.get("spec", ""),
                "broad_line": r.get("broad_line", ""),
                "xray": r.get("xray", ""),
                "variable": r.get("variable", ""),
                "f444w": float(r["f444w"]) if r.get("f444w") else None,
                "notes": r.get("notes", ""),
                "corrected": "",
            })
        meta["n_rows"] = len(rows)
        papers.append(meta)
    return papers, entries


def apply_corrections(entries):
    """Apply data/corrections.yaml on top of the published tables."""
    fixes = yaml.safe_load(CORRECTIONS.read_text()) if CORRECTIONS.exists() else []
    index = {(e["paper"], e["id"]): e for e in entries}
    for fx in fixes or []:
        e = index.get((fx["paper"], str(fx["id"])))
        if e is None:
            print(f"correction not applied, no row {fx['paper']}:{fx['id']}")
            continue
        for k in ("ra", "dec", "z", "z_type"):
            if k in fx:
                e[k] = fx[k] if fx[k] is not None else (None if k == "z" else "")
        e["corrected"] = fx["reason"]
    return len(fixes or [])


def group(entries, radius_arcsec):
    """Friends-of-friends grouping; returns a list of index lists."""
    n = len(entries)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    c = SkyCoord([e["ra"] for e in entries] * u.deg, [e["dec"] for e in entries] * u.deg)
    i1, i2, _, _ = search_around_sky(c, c, radius_arcsec * u.arcsec)
    for a, b in zip(i1, i2):
        if a < b:
            ra_, rb_ = find(a), find(b)
            if ra_ != rb_:
                parent[rb_] = ra_
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def sep_arcsec(ra1, dec1, ra2, dec2):
    """Angular separation (haversine), broadcasting over numpy arrays."""
    ra1, dec1, ra2, dec2 = (np.radians(np.asarray(x, dtype=float)) for x in (ra1, dec1, ra2, dec2))
    h = np.sin((dec2 - dec1) / 2) ** 2 + np.cos(dec1) * np.cos(dec2) * np.sin((ra2 - ra1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))) * 3600


def mean_position(ras, decs):
    ra, dec = np.radians(ras), np.radians(decs)
    v = np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)]).mean(axis=1)
    return float(np.degrees(np.arctan2(v[1], v[0])) % 360), float(np.degrees(np.arctan2(v[2], np.hypot(v[0], v[1]))))


def jname(ra, dec):
    """IAU-style name; components are truncated, not rounded."""
    t = int(ra / 15 * 3600 * 100)            # hundredths of a second of time
    hh, rem = divmod(t, 3600 * 100)
    mm, ss = divmod(rem, 60 * 100)
    a = int(abs(dec) * 3600 * 10)            # tenths of an arcsec
    dd, rem = divmod(a, 3600 * 10)
    dm, ds = divmod(rem, 60 * 10)
    sign = "-" if dec < 0 else "+"
    return f"LRDZ J{hh:02d}{mm:02d}{ss // 100:02d}.{ss % 100:02d}{sign}{dd:02d}{dm:02d}{ds // 10:02d}.{ds % 10}"


def fields_of(ras, decs, fallbacks):
    """Field label for each object: the deep field it lies in, else the papers' own field name."""
    out = [None] * len(ras)
    for name, fra, fdec, rad in FIELDS:
        inside = sep_arcsec(ras, decs, fra, fdec) / 3600 < rad
        for i in np.flatnonzero(inside):
            out[i] = out[i] or name
    for i, f in enumerate(out):
        if f is None:
            named = [x for x in fallbacks[i] if x]
            out[i] = max(set(named), key=named.count) if named else "Other"
    return out


def tri(values):
    """Combine per-paper 1/0/'' flags: 1 if any paper says yes, 0 if tested and never yes."""
    if "1" in values:
        return 1
    if "0" in values:
        return 0
    return None


def assign_names(objects, radius_arcsec):
    registry = json.loads(ID_REGISTRY.read_text()) if ID_REGISTRY.exists() else {}
    names = list(registry)
    candidates = [[] for _ in objects]
    if names and objects:
        oc = SkyCoord([o["ra"] for o in objects] * u.deg, [o["dec"] for o in objects] * u.deg)
        rc = SkyCoord([registry[k][0] for k in names] * u.deg, [registry[k][1] for k in names] * u.deg)
        io, ir, sep, _ = search_around_sky(oc, rc, 2 * radius_arcsec * u.arcsec)
        for a, b, d in zip(io, ir, sep.arcsec):
            candidates[a].append((d, names[b]))
    used = set()
    for o, cands in zip(objects, candidates):
        name = next((n for _, n in sorted(cands) if n not in used), None)
        if name is None:
            base = name = jname(o["ra"], o["dec"])
            k = 2
            while name in registry or name in used:
                name, k = f"{base}-{k}", k + 1
            registry[name] = [round(o["ra"], 7), round(o["dec"], 7)]
        used.add(name)
        o["name"] = name
    ID_REGISTRY.write_text(json.dumps(dict(sorted(registry.items())), indent=0) + "\n")


def build_objects(entries, groups, papers_by_key):
    objects = []
    for idx in groups:
        es = sorted((entries[i] for i in idx), key=lambda e: (e["year"], e["paper"]))
        ras, decs = np.array([e["ra"] for e in es]), np.array([e["dec"] for e in es])
        ra, dec = mean_position(ras, decs)
        seps = sep_arcsec(ra, dec, ras, decs)
        with_z = [e for e in es if e["z"] is not None]
        best = min(with_z, key=lambda e: (Z_RANK.get(e["z_type"], 3), -e["year"])) if with_z else None
        tags = set()
        for e in es:
            tags.update(papers_by_key[e["paper"]].get("tags") or [])
        xr = [e["xray"] for e in es]
        f444 = [e["f444w"] for e in es if e["f444w"] is not None]
        lrd_votes = [e for e in es if e["lrd"]]
        objects.append({
            "ra": round(ra, 7),
            "dec": round(dec, 7),
            "field": [e["field"] for e in es],  # replaced by fields_of() below
            "z": round(best["z"], 4) if best else None,
            "z_type": best["z_type"] if best else "",
            "z_ref": best["paper"] if best else "",
            "lrd": bool(lrd_votes),
            "lrd_contested": bool(lrd_votes) and any(e["lrd_flag"] == "0" for e in es),
            "spec": any(e["spec"] for e in es) or any(e["z_type"] in ("spec", "grism") for e in es),
            "broad_line": tri([e["broad_line"] for e in es]),
            "xray": "det" if "det" in xr else ("nondet" if "nondet" in xr else None),
            "variable": tri([e["variable"] for e in es]),
            "miri": "miri" in tags,
            "jwst": any(papers_by_key[e["paper"]]["facility"] == "JWST" for e in es),
            "f444w": round(float(np.median(f444)), 2) if f444 else None,
            "first_year": es[0]["year"],
            "first_ref": es[0]["paper"],
            "n_papers": len({e["paper"] for e in es}),
            "max_sep": round(float(seps.max()), 3),
            "entries": [
                {k: e[k] for k in ("paper", "id", "z", "z_type", "spec", "broad_line", "xray", "variable", "notes", "corrected")}
                | {"ra": round(e["ra"], 7), "dec": round(e["dec"], 7), "lrd": "1" if e["lrd"] else e["lrd_flag"],
                   "sep": round(float(s), 3)}
                for e, s in zip(es, seps)
            ],
        })
    for o, f in zip(objects, fields_of(np.array([o["ra"] for o in objects]), np.array([o["dec"] for o in objects]),
                                      [o["field"] for o in objects])):
        o["field"] = f
    objects.sort(key=lambda o: o["ra"])
    return objects


def bibtex(p):
    names = re.split(r"(?<=\.),\s+", p.get("authors") or f"{p['first_author']}, et al.")
    names = ["others" if n.strip(" ,") in ("et al.", "et al") else n.strip(" ,") for n in names]
    fields = {
        "author": " and ".join(names),
        "title": "{" + p["title"] + "}",
        "year": str(p["year"]),
        "journal": (p.get("journal") or "arXiv e-prints").split(",")[0],
        "eprint": str(p.get("arxiv") or ""),
        "archivePrefix": "arXiv" if p.get("arxiv") else "",
        "doi": p.get("doi") or "",
        "adsurl": f"https://ui.adsabs.harvard.edu/abs/{p['ads_bibcode']}" if p.get("ads_bibcode") else "",
    }
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items() if v)
    return f"@ARTICLE{{{p.get('ads_bibcode') or p['key']},\n{body}\n}}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=0.5, help="match radius in arcsec (default 0.5)")
    args = ap.parse_args()

    papers, entries = load_papers()
    if not entries:
        sys.exit("no valid papers found")
    n_fix = apply_corrections(entries)
    by_key = {p["key"]: p for p in papers}
    objects = build_objects(entries, group(entries, args.radius), by_key)
    assign_names(objects, args.radius)

    # per-paper statistics: unique objects, and how many it reported first
    for p in papers:
        mine = [o for o in objects if any(e["paper"] == p["key"] for e in o["entries"])]
        p["n_unique"] = len(mine)
        p["n_first"] = sum(o["first_ref"] == p["key"] for o in mine)
        p["n_lrd"] = sum(any(e["paper"] == p["key"] and e["lrd"] == "1" for e in o["entries"]) for o in mine)
    papers.sort(key=lambda p: (p["year"], p["key"]))

    BUILD.mkdir(parents=True, exist_ok=True)
    meta = {
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "match_radius_arcsec": args.radius,
        "n_objects": len(objects),
        "n_lrd": sum(o["lrd"] for o in objects),
        "n_entries": len(entries),
        "n_papers": len(papers),
        "n_spec": sum(o["spec"] and o["lrd"] for o in objects),
        "n_lrd_jwst": sum(o["lrd"] and o["jwst"] for o in objects),
    }
    for p in papers:
        p["bibtex"] = bibtex(p)
    paper_fields = ["key", "label", "first_author", "authors", "year", "title", "journal", "arxiv", "doi", "ads_bibcode",
                    "selection", "facility", "sample_is_lrd", "tags", "fields", "source_url", "source_note", "notes",
                    "n_rows", "n_unique", "n_first", "n_lrd", "bibtex"]
    out = {
        "meta": meta,
        "papers": [{k: p.get(k) for k in paper_fields} for p in papers],
        "objects": objects,
    }
    (BUILD / "lrdzoo.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

    cols = ["name", "ra", "dec", "field", "z", "z_type", "z_ref", "lrd", "lrd_contested", "spec", "broad_line",
            "xray", "variable", "miri", "jwst", "f444w", "first_year", "first_ref", "n_papers", "max_sep", "aliases", "refs"]
    with (BUILD / "lrdzoo_objects.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for o in objects:
            row = dict(o, aliases=";".join(e["id"] for e in o["entries"]),
                       refs=";".join(dict.fromkeys(e["paper"] for e in o["entries"])))
            w.writerow(["" if row[c] is None else int(row[c]) if isinstance(row[c], bool) else row[c] for c in cols])
    ecols = ["name", "paper", "id", "ra", "dec", "sep", "z", "z_type", "lrd", "spec", "broad_line", "xray", "variable", "notes",
             "corrected"]
    with (BUILD / "lrdzoo_entries.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(ecols)
        for o in objects:
            for e in o["entries"]:
                w.writerow([o["name"]] + ["" if e.get(c) is None else e.get(c) for c in ecols[1:]])
    (BUILD / "references.bib").write_text("\n".join(p["bibtex"] for p in papers))

    print(f"{meta['n_papers']} papers, {meta['n_entries']} entries -> {meta['n_objects']} unique objects "
          f"({meta['n_lrd']} LRDs, {meta['n_spec']} LRDs with spectra); match radius {args.radius}\"; "
          f"{n_fix} corrections applied")
    wide = sorted((o for o in objects if o["max_sep"] > 0.6 * args.radius and o["n_papers"] > 1), key=lambda o: -o["max_sep"])
    if wide:
        print(f"{len(wide)} merged objects whose papers' positions differ by more than {0.6 * args.radius:.2f}\" (largest first):")
        for o in wide[:10]:
            print(f"  {o['name']}: {o['max_sep']}\" ({', '.join(e['paper'] + ':' + e['id'] for e in o['entries'])})")
    dup = [o for o in objects if len(o["entries"]) > o["n_papers"]]
    if dup:
        by = {}
        for o in dup:
            for e in o["entries"]:
                if sum(x["paper"] == e["paper"] for x in o["entries"]) > 1:
                    by.setdefault(e["paper"], set()).add(o["name"])
        print("objects listed more than once by the same paper: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(by.items())))


if __name__ == "__main__":
    main()
