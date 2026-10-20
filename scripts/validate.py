#!/usr/bin/env python3
"""Validate every paper folder under data/papers/.

Each paper lives in data/papers/<key>/ with two files:
  meta.yaml    - bibliographic + provenance metadata (see README "Adding a paper")
  objects.csv  - one row per object, as listed in that paper

Usage:
  python scripts/validate.py            # validate all papers
  python scripts/validate.py kocevski2025 greene2024
Exit code is non-zero if any paper has errors (warnings do not fail).
"""
import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "data" / "papers"

SELECTIONS = {
    "photometric",   # colour / compactness / SED selected from imaging
    "spectroscopic", # NIRSpec (or ground) spectra, usually broad Balmer lines
    "grism",         # NIRCam/NIRISS slitless spectroscopy
    "variability",   # multi-epoch photometry / spectroscopy
    "xray",          # X-ray detections or stacks
    "radio",         # radio detections or limits
    "infrared",      # MIRI / ALMA / far-IR follow-up
    "compilation",   # re-analysis of objects from earlier papers
    "individual",    # one or a few notable objects
    "local",         # low-redshift analogues
}
TAGS = {"nirspec", "grism", "photometry", "xray", "variability", "miri", "alma", "radio", "ground-spec"}
Z_TYPES = {"spec", "grism", "phot", ""}
SPEC = {"", "NIRSpec/PRISM", "NIRSpec/grating", "NIRSpec", "NIRCam/grism", "NIRISS/grism", "ground"}
TRI = {"", "1", "0"}
XRAY = {"", "det", "nondet"}

REQUIRED_META = ["key", "first_author", "year", "title", "selection", "n_objects", "source_url", "source_note"]
REQUIRED_COLS = ["id", "ra", "dec"]
OPTIONAL_COLS = ["z", "z_type", "field", "lrd", "spec", "broad_line", "xray", "variable", "f444w", "notes"]


def check_paper(folder: Path):
    errors, warnings = [], []
    meta_path, obj_path = folder / "meta.yaml", folder / "objects.csv"
    if not meta_path.exists():
        return [f"missing {meta_path.name}"], warnings
    if not obj_path.exists():
        return [f"missing {obj_path.name}"], warnings

    meta = yaml.safe_load(meta_path.read_text()) or {}
    for k in REQUIRED_META:
        if meta.get(k) in (None, ""):
            errors.append(f"meta.yaml: missing '{k}'")
    if meta.get("key") and meta["key"] != folder.name:
        errors.append(f"meta.yaml: key '{meta['key']}' != folder name '{folder.name}'")
    if not (meta.get("arxiv") or meta.get("doi")):
        errors.append("meta.yaml: need at least one of 'arxiv' or 'doi'")
    if meta.get("arxiv") and not re.fullmatch(r"\d{4}\.\d{4,5}", str(meta["arxiv"])):
        errors.append(f"meta.yaml: arxiv '{meta['arxiv']}' should look like 2404.03576 (no version, no prefix)")
    if meta.get("selection") and meta["selection"] not in SELECTIONS:
        errors.append(f"meta.yaml: selection '{meta['selection']}' not in {sorted(SELECTIONS)}")
    if "sample_is_lrd" in meta and not isinstance(meta["sample_is_lrd"], bool):
        errors.append("meta.yaml: sample_is_lrd must be true or false")
    for t in meta.get("tags") or []:
        if t not in TAGS:
            errors.append(f"meta.yaml: tag '{t}' not in {sorted(TAGS)}")

    with obj_path.open(newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)
    for c in REQUIRED_COLS:
        if c not in cols:
            errors.append(f"objects.csv: missing column '{c}'")
    unknown = [c for c in cols if c not in REQUIRED_COLS + OPTIONAL_COLS]
    if unknown:
        errors.append(f"objects.csv: unknown columns {unknown}")
    if errors:
        return errors, warnings

    ids, coords = set(), set()
    for i, r in enumerate(rows, start=2):
        loc = f"objects.csv line {i} ({r.get('id')})"
        try:
            ra, dec = float(r["ra"]), float(r["dec"])
        except ValueError:
            errors.append(f"{loc}: ra/dec must be decimal degrees")
            continue
        if not (0 <= ra < 360 and -90 <= dec <= 90):
            errors.append(f"{loc}: ra/dec out of range ({ra}, {dec})")
        if r["id"] in ids:
            errors.append(f"{loc}: duplicate id")
        ids.add(r["id"])
        key = (round(ra, 6), round(dec, 6))
        if key in coords:
            warnings.append(f"{loc}: identical coordinates to an earlier row")
        coords.add(key)
        z = (r.get("z") or "").strip()
        if z:
            try:
                zf = float(z)
                if not 0 <= zf <= 20:
                    errors.append(f"{loc}: z={zf} out of range")
            except ValueError:
                errors.append(f"{loc}: z '{z}' not a number")
        if (r.get("z_type") or "") not in Z_TYPES:
            errors.append(f"{loc}: z_type '{r.get('z_type')}' not in {sorted(Z_TYPES)}")
        if z and not r.get("z_type"):
            warnings.append(f"{loc}: z given without z_type")
        if (r.get("spec") or "") not in SPEC:
            errors.append(f"{loc}: spec '{r.get('spec')}' not in {sorted(SPEC)}")
        for c in ("lrd", "broad_line", "variable"):
            if (r.get(c) or "") not in TRI:
                errors.append(f"{loc}: {c} must be 1, 0 or empty")
        if (r.get("xray") or "") not in XRAY:
            errors.append(f"{loc}: xray must be det, nondet or empty")

    if meta.get("sample_is_lrd") is False and not any(r.get("lrd") == "1" for r in rows):
        warnings.append("sample_is_lrd is false but no row has lrd=1, so no object counts as an LRD")
    n = meta.get("n_objects")
    if isinstance(n, int) and n != len(rows):
        warnings.append(f"n_objects={n} in meta.yaml but objects.csv has {len(rows)} rows")
    return errors, warnings


def main(argv):
    keys = argv[1:] or sorted(p.name for p in PAPERS.iterdir() if p.is_dir())
    bad = 0
    for k in keys:
        errs, warns = check_paper(PAPERS / k)
        status = "FAIL" if errs else "ok"
        print(f"[{status}] {k}")
        for e in errs:
            print(f"    error: {e}")
        for w in warns:
            print(f"    warn:  {w}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
