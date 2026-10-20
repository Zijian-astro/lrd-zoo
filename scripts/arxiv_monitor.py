#!/usr/bin/env python3
"""Check arXiv for new little-red-dot papers and keep data/arxiv_inbox.json up to date.

Every paper whose title or abstract mentions "little red dot(s)" or "LRDs" is added to the
inbox. Its status is
  in_zoo   - its arXiv ID is in some data/papers/*/meta.yaml
  ignored  - listed in data/arxiv_ignore.yaml (theory papers, no object table, ...)
  todo     - still to be looked at
The web page shows the inbox, with a "may contain a sample" hint when the
abstract mentions a number of objects or a catalogue.

Usage:
  python scripts/arxiv_monitor.py                 # last 30 days
  python scripts/arxiv_monitor.py --days 365      # backfill
  python scripts/arxiv_monitor.py --open-issues   # also open a GitHub issue per new 'todo' paper
                                                  # (needs GH_TOKEN and GITHUB_REPOSITORY, as in GitHub Actions)
"""
import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "arxiv_inbox.json"
IGNORE = ROOT / "data" / "arxiv_ignore.yaml"
API = "https://export.arxiv.org/api/query"
QUERY = ('(ti:"little red dot" OR ti:"little red dots" OR abs:"little red dot" OR abs:"little red dots" OR abs:LRDs)'
         ' AND (cat:astro-ph.GA OR cat:astro-ph.CO OR cat:astro-ph.HE OR cat:astro-ph.SR)')
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
SAMPLE_HINT = re.compile(
    r"\b(\d{2,5}|dozens|hundreds)\s+(?:\w+\s+){0,3}(LRDs?|little red dots?|sources|objects|candidates|AGNs?|galaxies)\b"
    r"|\bcatalog(?:ue)?s?\b|\bsample of\b|\bcensus\b",
    re.I,
)
MAX_ISSUES_PER_RUN = 10


def known_arxiv_ids():
    ids = {}
    for meta in (ROOT / "data" / "papers").glob("*/meta.yaml"):
        m = yaml.safe_load(meta.read_text()) or {}
        if m.get("arxiv"):
            ids[str(m["arxiv"])] = m["key"]
    return ids


def ignored_ids():
    if not IGNORE.exists():
        return {}
    return {str(k): v for k, v in (yaml.safe_load(IGNORE.read_text()) or {}).items()}


def fetch(days):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out, start, page = [], 0, 100
    while True:
        params = urllib.parse.urlencode({"search_query": QUERY, "sortBy": "submittedDate",
                                         "sortOrder": "descending", "start": start, "max_results": page})
        req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": "lrd-zoo-monitor/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            root = ET.fromstring(r.read())
        entries = root.findall("a:entry", ATOM)
        if not entries:
            break
        for e in entries:
            published = dt.datetime.fromisoformat(e.findtext("a:published", namespaces=ATOM).replace("Z", "+00:00"))
            if published < since:
                return out
            arxiv_id = re.sub(r"v\d+$", "", e.findtext("a:id", namespaces=ATOM).rsplit("/abs/", 1)[-1])
            abstract = " ".join(e.findtext("a:summary", namespaces=ATOM).split())[:1500]
            out.append({
                "arxiv": arxiv_id,
                "title": " ".join(e.findtext("a:title", namespaces=ATOM).split()),
                "authors": [a.findtext("a:name", namespaces=ATOM) for a in e.findall("a:author", ATOM)],
                "published": published.date().isoformat(),
                "primary": e.find("arxiv:primary_category", ATOM).get("term"),
                "journal_ref": e.findtext("arxiv:journal_ref", namespaces=ATOM),
                "sample_hint": bool(SAMPLE_HINT.search(abstract)),
                "abstract": abstract,
            })
        start += page
        time.sleep(3)  # arXiv API etiquette
    return out


def open_issue(paper):
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN")
    if not (repo and token):
        print("  (no GH_TOKEN / GITHUB_REPOSITORY; not opening an issue)")
        return
    authors = ", ".join(paper["authors"][:6]) + (" et al." if len(paper["authors"]) > 6 else "")
    body = (f"**{paper['title']}**\n{authors}\n\nhttps://arxiv.org/abs/{paper['arxiv']} "
            f"(submitted {paper['published']})\n\n> {paper['abstract'][:1200]}\n\n"
            f"- [ ] Does it list objects with coordinates? If yes, add `data/papers/<key>/` (see data/SCHEMA.md)\n"
            f"- [ ] Otherwise add `\"{paper['arxiv']}\": <reason>` to data/arxiv_ignore.yaml\n")
    labels = ["new-paper"] + (["has-sample"] if paper["sample_hint"] else [])
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues", method="POST",
        data=json.dumps({"title": f"[arXiv {paper['arxiv']}] {paper['title']}", "body": body, "labels": labels}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"  opened issue {json.load(r)['html_url']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="look back this many days (default 30)")
    ap.add_argument("--open-issues", action="store_true", help="open a GitHub issue for each new 'todo' paper")
    args = ap.parse_args()

    inbox = json.loads(INBOX.read_text()) if INBOX.exists() else {"papers": []}
    by_id = {p["arxiv"]: p for p in inbox["papers"]}
    known, ignored = known_arxiv_ids(), ignored_ids()
    today = dt.date.today().isoformat()

    new = []
    for p in fetch(args.days):
        if p["arxiv"] not in by_id:
            p["first_seen"] = today
            by_id[p["arxiv"]] = p
            new.append(p)
        else:
            by_id[p["arxiv"]].update({k: p[k] for k in ("title", "authors", "journal_ref", "sample_hint", "abstract")})

    for p in by_id.values():
        if p["arxiv"] in known:
            p["status"], p["zoo_key"] = "in_zoo", known[p["arxiv"]]
        elif p["arxiv"] in ignored:
            p["status"], p["ignore_reason"] = "ignored", ignored[p["arxiv"]]
        else:
            p["status"] = "todo"

    papers = sorted(by_id.values(), key=lambda p: (p["published"], p["arxiv"]), reverse=True)
    INBOX.write_text(json.dumps({"updated": today, "query": QUERY, "papers": papers}, indent=1, ensure_ascii=False) + "\n")
    todo = [p for p in new if p["status"] == "todo"]
    print(f"{len(new)} new paper(s), {len(todo)} to review; inbox has {len(papers)} papers")
    for p in todo:
        print(f"  {p['arxiv']}  {'[sample?] ' if p['sample_hint'] else ''}{p['title'][:90]}")
    if args.open_issues:
        for p in todo[:MAX_ISSUES_PER_RUN]:
            open_issue(p)


if __name__ == "__main__":
    main()
