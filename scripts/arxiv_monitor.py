#!/usr/bin/env python3
"""Check arXiv (and VizieR, and optionally ADS) for new little-red-dot papers and keep
data/arxiv_inbox.json up to date.

Every paper whose title or abstract mentions "little red dot(s)" or "LRDs" is added to the
inbox. Its status is
  in_zoo   - its arXiv ID is in some data/papers/*/meta.yaml
  ignored  - listed in data/arxiv_ignore.yaml (theory papers, no object table, ...)
  todo     - still to be looked at
The web page shows the inbox, with a "may contain a sample" hint when the
abstract mentions a number of objects or a catalogue.

Two more sources feed the inbox:
  VizieR  - always. A keyword search finds catalogues about LRDs, and published papers in the inbox
            are looked up by their VizieR name (from the journal reference or the ADS bibcode). A paper
            with a VizieR table gets "vizier": [names]; the catalogues are listed under the top-level
            "vizier" key (with first_seen), including LRD catalogues that match no paper here.
  ADS     - only when ADS_API_TOKEN is set. A full-text search finds papers that mention little red
            dots only in the body ("fulltext_only": true), and every inbox paper gets its
            journal bibcode and DOI, which make the VizieR lookup exact.

Usage:
  python scripts/arxiv_monitor.py                 # last 30 days
  python scripts/arxiv_monitor.py --days 365      # backfill
  python scripts/arxiv_monitor.py --open-issues   # also open/label GitHub issues (see open_issues)
                                                  # (needs GH_TOKEN and GITHUB_REPOSITORY, as in GitHub Actions)
"""
import argparse
import datetime as dt
import json
import os
import re
import time
import unicodedata
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
UA = {"User-Agent": "lrd-zoo-monitor/1.1 (https://github.com/Zijian-astro/lrd-zoo)"}

VIZIER = "https://vizier.cds.unistra.fr/viz-bin/asu-tsv"
VIZIER_WORDS = ["little red dot", "LRDs"]  # -words searches catalogue titles, descriptions and authors
VIZIER_ANCHOR = "J/A+A/693/L2"  # a catalogue that exists, added to every -source lookup (see update_vizier)
ADS = "https://api.adsabs.harvard.edu/v1/search/query"
ADS_FULLTEXT = 'full:("little red dot" OR "little red dots") collection:astronomy'
# bibcode journal -> VizieR journal (VizieR names are J/<journal>/<volume>/<page>)
BIB_JOURNAL = {"A&A": "A+A", "ApJ": "ApJ", "ApJS": "ApJS", "AJ": "AJ", "MNRAS": "MNRAS", "PASJ": "PASJ", "PASP": "PASP"}
# journal_ref as authors type it on arXiv -> VizieR name; letters journals put an L before the page
JREF = [
    (re.compile(r"\bA&A,?\s+(\d+),?\s+(?:\(\d{4}\),?\s+)?([AL]?\d+)\b"), "A+A", ""),
    (re.compile(r"(?:\bApJL|\bApJ\s?Lett?\.?|\bAstrophys\.\s?J\.\s?Lett\.?|\bThe Astrophysical Journal Letters)"
                r",?\s+(\d+),?\s+(?:\(\d{4}\),?\s+)?(?:\d+,\s+)?L?(\d+)\b"), "ApJ", "L"),
    (re.compile(r"(?:\bApJS|\bAstrophys\.\s?J\.\s?Suppl\.?)"
                r",?\s+(\d+),?\s+(?:\(\d{4}\),?\s+)?(?:\d+,\s+)?(\d+)\b"), "ApJS", ""),
    (re.compile(r"(?:\bApJ|\bAstrophys\.\s?J\.|\bThe Astrophysical Journal)"
                r",?\s+(\d+),?\s+(?:\(\d{4}\),?\s+)?(?:\d+,\s+)?(\d+)\b"), "ApJ", ""),
    (re.compile(r"\bAJ,?\s+(\d+),?\s+(?:\(\d{4}\),?\s+)?(\d+)\b"), "AJ", ""),
]


def http(url, data=None, headers=None, method=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def known_papers():
    """arXiv ID -> key and ADS bibcode -> key for every paper already in the zoo."""
    ids, bibs = {}, {}
    for meta in (ROOT / "data" / "papers").glob("*/meta.yaml"):
        m = yaml.safe_load(meta.read_text()) or {}
        if m.get("arxiv"):
            ids[str(m["arxiv"])] = m["key"]
        if m.get("ads_bibcode"):
            bibs[str(m["ads_bibcode"])] = m["key"]
    return ids, bibs


def ignored_ids():
    if not IGNORE.exists():
        return {}
    return {str(k): v for k, v in (yaml.safe_load(IGNORE.read_text()) or {}).items()}


# ---------- arXiv ----------

def parse_entry(e):
    published = dt.datetime.fromisoformat(e.findtext("a:published", namespaces=ATOM).replace("Z", "+00:00"))
    abstract = " ".join(e.findtext("a:summary", namespaces=ATOM).split())[:1500]
    p = {
        "arxiv": re.sub(r"v\d+$", "", e.findtext("a:id", namespaces=ATOM).rsplit("/abs/", 1)[-1]),
        "title": " ".join(e.findtext("a:title", namespaces=ATOM).split()),
        "authors": [a.findtext("a:name", namespaces=ATOM) for a in e.findall("a:author", ATOM)],
        "published": published.date().isoformat(),
        "primary": e.find("arxiv:primary_category", ATOM).get("term"),
        "journal_ref": e.findtext("arxiv:journal_ref", namespaces=ATOM),
        "sample_hint": bool(SAMPLE_HINT.search(abstract)),
        "abstract": abstract,
    }
    doi = e.findtext("arxiv:doi", namespaces=ATOM)
    if doi:
        p["doi"] = doi.strip()
    return p, published


def fetch(days):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out, start, page = [], 0, 100
    while True:
        params = urllib.parse.urlencode({"search_query": QUERY, "sortBy": "submittedDate",
                                         "sortOrder": "descending", "start": start, "max_results": page})
        entries = ET.fromstring(http(f"{API}?{params}")).findall("a:entry", ATOM)
        if not entries:
            break
        for e in entries:
            p, published = parse_entry(e)
            if published < since:
                return out
            out.append(p)
        start += page
        time.sleep(3)  # arXiv API etiquette
    return out


def fetch_ids(ids):
    """arXiv metadata for specific IDs (papers found by ADS)."""
    out = []
    for i in range(0, len(ids), 50):
        params = urllib.parse.urlencode({"id_list": ",".join(ids[i:i + 50]), "max_results": 50})
        out += [parse_entry(e)[0] for e in ET.fromstring(http(f"{API}?{params}")).findall("a:entry", ATOM)
                if e.find("a:title", ATOM) is not None and e.find("arxiv:primary_category", ATOM) is not None]
        time.sleep(3)
    return out


# ---------- ADS (optional) ----------

def ads_search(token, q, fl, rows=200):
    docs, start = [], 0
    while True:
        params = urllib.parse.urlencode({"q": q, "fl": fl, "rows": rows, "start": start, "sort": "entdate desc"})
        r = json.loads(http(f"{ADS}?{params}", headers={"Authorization": f"Bearer {token}"}))["response"]
        docs += r["docs"]
        start += rows
        if start >= r["numFound"] or not r["docs"]:
            return docs


def ads_arxiv_id(doc):
    for ident in doc.get("identifier", []):
        m = re.fullmatch(r"arXiv:(\d{4}\.\d{4,5})", ident)
        if m:
            return m.group(1)
    return None


def ads_fulltext(token, days):
    """arXiv IDs of papers ADS added in the last `days` days that mention LRDs anywhere in the text."""
    docs = ads_search(token, f"{ADS_FULLTEXT} entdate:[NOW-{days}DAYS TO *]", "bibcode,identifier")
    ids = {ads_arxiv_id(d) for d in docs}
    print(f"ADS full text: {len(docs)} records, {len(ids - {None})} with an arXiv ID")
    return sorted(ids - {None})


def ads_enrich(token, papers):
    """Add the journal bibcode, DOI and ADS data links (CDS = VizieR) to inbox papers."""
    by_id = {p["arxiv"]: p for p in papers}
    ids = list(by_id)
    for i in range(0, len(ids), 50):
        q = "identifier:(" + " OR ".join(f'"arXiv:{a}"' for a in ids[i:i + 50]) + ")"
        for d in ads_search(token, q, "bibcode,identifier,doi,data"):
            p = by_id.get(ads_arxiv_id(d))
            if not p:
                continue
            if "arXiv" not in d["bibcode"]:
                p["bibcode"] = d["bibcode"]
            if d.get("doi") and not p.get("doi"):
                p["doi"] = d["doi"][0]
            p["ads_cds"] = any(x.split(":")[0] in ("CDS", "Vizier") for x in d.get("data", []))
        time.sleep(1)


# ---------- VizieR ----------

def vizier_meta(**params):
    """Catalogue-level metadata from VizieR's ASU interface (no table rows)."""
    q = urllib.parse.urlencode({"-meta": "", "-out.max": 0, **params})
    cats, cur, in_table = [], None, False
    for line in http(f"{VIZIER}?{q}", timeout=120).decode("utf-8", "replace").splitlines():
        if line.startswith("#RESOURCE="):
            cur, in_table = {}, False
            cats.append(cur)
        elif cur is None:
            continue
        elif line.startswith("#Table"):
            in_table = True
        elif not in_table and line.startswith("#Name:"):
            cur["name"] = line.split(":", 1)[1].strip()
        elif not in_table and line.startswith("#Title:"):
            cur["title"] = line.split(":", 1)[1].strip()
        elif not in_table and line.startswith("#INFO\t"):
            key, _, val = line[6:].partition("=")
            val = val.split("\t")[0].strip()
            if key == "creator":
                cur["creator"] = val
            elif key == "cites" and val.startswith("bibcode:"):
                cur.setdefault("bibcode", val[8:])
            elif key == "original_date":
                cur["year"] = int(val[:4]) if val[:4].isdigit() else None
            elif key == "publication_date":
                cur["published"] = val
    return [c for c in cats if c.get("name", "").startswith("J/")]


def vizier_name_from_bibcode(bib):
    """2025A&A...702A..57H -> J/A+A/702/A57; 2024ApJ...969L..13W -> J/ApJ/969/L13."""
    if len(bib) != 19:
        return None
    journal, vol = BIB_JOURNAL.get(bib[4:9].strip(".")), bib[9:13].strip(".")
    page = bib[13:18].strip(".") if bib[13].isdigit() else bib[13].strip(".") + bib[14:18].strip(".")
    return f"J/{journal}/{vol}/{page}" if journal and vol.isdigit() and page else None


def vizier_name_from_jref(jref):
    for rx, journal, letter in JREF:
        m = rx.search(jref or "")
        if m:
            page = m.group(2)
            return f"J/{journal}/{m.group(1)}/{letter if letter and page[0].isdigit() else ''}{page}"
    return None


def ascii_lower(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()


def same_author_and_year(cat, author, year):
    """Is the VizieR creator ('de Graaff A.', 'Hviding R.E.') this first author, and the year plausible?"""
    toks = (cat.get("creator") or "").split()
    while len(toks) > 1 and re.fullmatch(r"(?:[A-Z][a-z]?\.-?)+|[A-Z]", toks[-1]):
        toks.pop()
    surname, a = ascii_lower(" ".join(toks)), ascii_lower(author)
    year_ok = cat.get("year") is not None and 0 <= cat["year"] - int(year) <= 2
    return bool(surname) and year_ok and (a == surname or a.endswith(" " + surname))


def update_vizier(registry, papers, zoo_bibs):
    """Search VizieR, add catalogues to `registry` (name -> info) and link each to a paper.

    Links, most exact first: the catalogue cites the paper's ADS bibcode; the catalogue name is the one
    derived from the paper's bibcode or journal reference, and the first author and year agree; the
    catalogue came from the LRD keyword search and exactly one inbox paper has the same first author and
    a plausible year.
    """
    found = {}
    for w in VIZIER_WORDS:
        for c in vizier_meta(**{"-words": w}):
            found[c["name"]] = {**c, "via": "keywords"}
        time.sleep(1)

    linked = {n for n, c in registry.items() if c.get("arxiv")}
    expected = {}  # VizieR name derived from the paper's bibcode or journal reference -> paper
    for p in papers:
        name = vizier_name_from_bibcode(p.get("bibcode") or "") or vizier_name_from_jref(p.get("journal_ref"))
        if name and not any(n in linked for n in p.get("vizier", [])):
            expected[name] = p
    names = sorted(set(expected) - set(found))
    for i in range(0, len(names), 40):
        # When none of the requested catalogues exists, VizieR falls back to a slow search that returns
        # hundreds of unrelated catalogues; one catalogue that does exist (Perger+25) prevents that.
        for c in vizier_meta(**{"-source": " ".join([VIZIER_ANCHOR] + names[i:i + 40])}):
            if c["name"] in expected:
                found.setdefault(c["name"], {**c, "via": "lookup"})
        time.sleep(1)
    # ADS says there is CDS data but the name could not be derived (other journals): exact bibcode search
    extra = [p for p in papers if p.get("ads_cds") and p.get("bibcode")
             and not any(c.get("bibcode") == p["bibcode"] for c in found.values())][:20]
    for p in extra:
        for c in vizier_meta(**{"-words": p["bibcode"]}):
            if c.get("bibcode") == p["bibcode"]:
                found.setdefault(c["name"], {**c, "via": "lookup"})
        time.sleep(1)

    today = dt.date.today().isoformat()
    for name, c in found.items():
        info = registry.setdefault(name, {"first_seen": today})
        info.update({k: c[k] for k in ("title", "creator", "bibcode", "year", "published") if c.get(k) is not None})

    by_bib = {p["bibcode"]: p for p in papers if p.get("bibcode")}
    by_zoo = {p["zoo_key"]: p for p in papers if p.get("zoo_key")}
    by_arxiv = {p["arxiv"]: p for p in papers}
    for name, info in registry.items():
        p = by_bib.get(info.get("bibcode")) or by_zoo.get(zoo_bibs.get(info.get("bibcode")))
        if p is None and name in expected:
            q = expected[name]
            p = q if q["authors"] and same_author_and_year(info, q["authors"][0], q["published"][:4]) else None
        if p is None and not info.get("arxiv") and found.get(name, {}).get("via") == "keywords":
            cands = [q for q in papers if q["authors"] and same_author_and_year(info, q["authors"][0], q["published"][:4])]
            p = cands[0] if len(cands) == 1 else None
        if p is not None:
            info["arxiv"] = p["arxiv"]
        zoo = zoo_bibs.get(info.get("bibcode")) or by_arxiv.get(info.get("arxiv"), {}).get("zoo_key")
        if zoo:
            info["zoo"] = zoo

    for p in papers:
        names = sorted(n for n, c in registry.items() if c.get("arxiv") == p["arxiv"])
        if names:
            p["vizier"] = names
        else:
            p.pop("vizier", None)


# ---------- GitHub issues ----------

def gh(method, path, data=None):
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN")
    body = json.dumps(data).encode() if data is not None else None
    return json.loads(http(f"https://api.github.com/repos/{repo}/{path}", data=body, method=method, timeout=30,
                           headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}) or b"null")


def existing_issues():
    """arXiv ID or VizieR name -> issue, for every issue the monitor opened (open or closed)."""
    out, page = {}, 1
    while True:
        batch = gh("GET", f"issues?state=all&labels=new-paper&per_page=100&page={page}")
        for i in batch:
            m = re.match(r"\[(?:arXiv|VizieR) ([^\]]+)\]", i["title"])
            if m:
                out[m.group(1)] = i
        if len(batch) < 100:
            return out
        page += 1


def vizier_lines(names, registry):
    return "".join(f"- VizieR **{n}**: {registry[n].get('title', '')} "
                   f"https://vizier.cds.unistra.fr/viz-bin/VizieR?-source={n}\n" for n in names)


def issue_body(paper, registry):
    authors = ", ".join(paper["authors"][:6]) + (" et al." if len(paper["authors"]) > 6 else "")
    found = ("\n_Found by the ADS full-text search: the abstract does not mention little red dots._\n"
             if paper.get("fulltext_only") else "")
    tables = f"\nMachine-readable table(s):\n{vizier_lines(paper['vizier'], registry)}" if paper.get("vizier") else ""
    return (f"**{paper['title']}**\n{authors}\n\nhttps://arxiv.org/abs/{paper['arxiv']} "
            f"(submitted {paper['published']})\n{found}{tables}\n> {paper['abstract'][:1200]}\n\n"
            f"- [ ] Does it list objects with coordinates? If yes, add `data/papers/<key>/` (see data/SCHEMA.md)\n"
            f"- [ ] Otherwise add `\"{paper['arxiv']}\": <reason>` to data/arxiv_ignore.yaml\n")


def open_issues(new, with_table, unmatched, registry):
    """Open an issue for each new 'todo' paper (abstract match, or any paper with a VizieR table). A 'todo'
    paper with a VizieR table gets labels 'has-sample' + 'vizier' and a comment on its open issue, or a new
    issue if it never had one; an LRD catalogue on VizieR that matches no paper gets its own issue.
    Every step checks the existing issues first, so a run that hits MAX_ISSUES_PER_RUN catches up later."""
    if not (os.environ.get("GITHUB_REPOSITORY") and os.environ.get("GH_TOKEN")):
        print("  (no GH_TOKEN / GITHUB_REPOSITORY; not opening issues)")
        return
    issues, opened = existing_issues(), 0

    def create(key, title, body, labels):
        nonlocal opened
        if key in issues or opened >= MAX_ISSUES_PER_RUN:
            return
        issues[key], opened = gh("POST", "issues", {"title": title, "body": body, "labels": labels}), opened + 1
        print(f"  opened issue {issues[key]['html_url']}")

    for p in with_table:
        issue = issues.get(p["arxiv"])
        if issue and issue["state"] == "open" and "vizier" not in {l["name"] for l in issue["labels"]}:
            gh("POST", f"issues/{issue['number']}/labels", {"labels": ["has-sample", "vizier"]})
            gh("POST", f"issues/{issue['number']}/comments",
               {"body": f"This paper has a table on VizieR:\n{vizier_lines(p['vizier'], registry)}"})
            print(f"  labelled issue #{issue['number']} (VizieR table)")
        create(p["arxiv"], f"[arXiv {p['arxiv']}] {p['title']}", issue_body(p, registry), ["new-paper", "has-sample", "vizier"])
    for p in new:
        if not p.get("fulltext_only"):
            labels = ["new-paper"] + (["has-sample"] if p["sample_hint"] else [])
            create(p["arxiv"], f"[arXiv {p['arxiv']}] {p['title']}", issue_body(p, registry), labels)
    for name in unmatched:
        c = registry[name]
        create(name, f"[VizieR {name}] {c.get('title', '')}",
               f"VizieR has a catalogue about little red dots that matches no paper in the inbox or the zoo:\n"
               f"{vizier_lines([name], registry)}\nADS: https://ui.adsabs.harvard.edu/abs/"
               f"{urllib.parse.quote(c.get('bibcode', ''))}\n\n"
               f"- [ ] Find the paper; if it lists objects with coordinates, add `data/papers/<key>/` (see data/SCHEMA.md)\n",
               ["new-paper", "has-sample", "vizier"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="look back this many days (default 30)")
    ap.add_argument("--open-issues", action="store_true", help="open/label GitHub issues for new papers and tables")
    args = ap.parse_args()

    inbox = json.loads(INBOX.read_text()) if INBOX.exists() else {"papers": []}
    by_id = {p["arxiv"]: p for p in inbox["papers"]}
    registry = inbox.get("vizier", {})
    known, zoo_bibs = known_papers()
    ignored = ignored_ids()
    today = dt.date.today().isoformat()
    token = os.environ.get("ADS_API_TOKEN")

    new = []
    for p in fetch(args.days):
        if p["arxiv"] not in by_id:
            p["first_seen"] = today
            by_id[p["arxiv"]] = p
            new.append(p)
        else:
            by_id[p["arxiv"]].update({k: p[k] for k in ("title", "authors", "journal_ref", "sample_hint", "abstract", "doi")
                                      if k in p})
            by_id[p["arxiv"]].pop("fulltext_only", None)
    if token:
        try:
            for p in fetch_ids([i for i in ads_fulltext(token, args.days) if i not in by_id]):
                p["first_seen"], p["fulltext_only"] = today, True
                by_id[p["arxiv"]] = p
                new.append(p)
        except Exception as e:  # ADS is optional; never let it stop the arXiv update
            print(f"ADS full-text search failed: {e}")

    for p in by_id.values():
        if p["arxiv"] in known:
            p["status"], p["zoo_key"] = "in_zoo", known[p["arxiv"]]
        elif p["arxiv"] in ignored:
            p["status"], p["ignore_reason"] = "ignored", ignored[p["arxiv"]]
        else:
            p["status"] = "todo"

    papers = sorted(by_id.values(), key=lambda p: (p["published"], p["arxiv"]), reverse=True)
    if token:
        try:
            ads_enrich(token, papers)
        except Exception as e:
            print(f"ADS bibcode lookup failed: {e}")
    before = {p["arxiv"]: set(p.get("vizier", [])) for p in papers}
    try:
        update_vizier(registry, papers, zoo_bibs)
    except Exception as e:  # keep last run's VizieR links
        print(f"VizieR check failed: {e}")
    for p in papers:
        p.pop("ads_cds", None)

    INBOX.write_text(json.dumps({"updated": today, "query": QUERY, "ads": bool(token), "papers": papers,
                                 "vizier": dict(sorted(registry.items()))}, indent=1, ensure_ascii=False) + "\n")

    todo = [p for p in new if p["status"] == "todo"]
    print(f"{len(new)} new paper(s), {len(todo)} to review; inbox has {len(papers)} papers")
    for p in todo:
        tags = ("[sample?] " if p["sample_hint"] else "") + ("[VizieR] " if p.get("vizier") else "") + \
               ("[full text] " if p.get("fulltext_only") else "")
        print(f"  {p['arxiv']}  {tags}{p['title'][:90]}")
    flagged = [p for p in papers if set(p.get("vizier", [])) - before.get(p["arxiv"], set())]
    unmatched = [n for n, c in registry.items() if not c.get("arxiv") and not c.get("zoo")]
    with_table = [p for p in papers if p.get("vizier")]
    print(f"VizieR: {len(registry)} catalogue(s) known, {len(with_table)} inbox paper(s) with a table "
          f"({sum(p['status'] == 'todo' for p in with_table)} to review)")
    for p in flagged:
        print(f"  new table for {p['arxiv']}: {', '.join(p['vizier'])}  {p['title'][:70]}")
    for n in unmatched:
        print(f"  LRD catalogue matching no paper: {n}  {registry[n].get('title', '')}")
    if args.open_issues:
        open_issues(todo, [p for p in with_table if p["status"] == "todo"], unmatched, registry)


if __name__ == "__main__":
    main()
