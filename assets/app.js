"use strict";

// Site settings. Set repoUrl once the GitHub repository exists.
const CONFIG = {
  repoUrl: "https://github.com/Zijian-astro/lrd-zoo",
  maintainer: "Zijian Zhang (KIAA, Peking University)",
  dataUrl: "data/build/lrdzoo.json",
  inboxUrl: "data/arxiv_inbox.json",
  pageSize: 100,
};

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtInt = (n) => Number(n).toLocaleString("en-US");
const pad2 = (n) => String(n).padStart(2, "0");
const slug = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
const norm = (s) => String(s || "").toLowerCase().replace(/[\s_\-–−.:+]/g, "");
const D2R = Math.PI / 180;

const state = {
  meta: null, papers: [], paperByKey: {}, objects: [], byDec: [], filtered: [],
  sort: { key: "ra", dir: 1 }, page: 0, chartsDirty: true, inbox: null, inboxFilter: null,
  lastQuery: [],
};

/* ---------- coordinates ---------- */
function fmtRA(ra) {
  let h = ra / 15, hh = Math.floor(h), m = (h - hh) * 60, mm = Math.floor(m), ss = Math.round((m - mm) * 6000) / 100;
  if (ss >= 60) { ss -= 60; mm += 1; }
  if (mm >= 60) { mm -= 60; hh += 1; }
  return `${pad2(hh % 24)}:${pad2(mm)}:${ss.toFixed(2).padStart(5, "0")}`;
}
function fmtDec(dec) {
  const sign = dec < 0 ? "-" : "+";
  let a = Math.abs(dec), d = Math.floor(a), m = (a - d) * 60, mm = Math.floor(m), ss = Math.round((m - mm) * 600) / 10;
  if (ss >= 60) { ss -= 60; mm += 1; }
  if (mm >= 60) { mm -= 60; d += 1; }
  return `${sign}${pad2(d)}:${pad2(mm)}:${ss.toFixed(1).padStart(4, "0")}`;
}
function sepArcsec(ra1, dec1, ra2, dec2) {
  const s = Math.sin(((dec2 - dec1) * D2R) / 2) ** 2 +
    Math.cos(dec1 * D2R) * Math.cos(dec2 * D2R) * Math.sin(((ra2 - ra1) * D2R) / 2) ** 2;
  return (2 * Math.asin(Math.min(1, Math.sqrt(s)))) / D2R * 3600;
}

const RE_NUM = /^[+-]?\d+(\.\d+)?$/;
const RE_SEXA = /^[+-]?\d{1,3}[:hd°]\d{1,2}[:m'′]\d{1,2}(\.\d*)?[s"″]?$/i;
const RE_JNAME = /J(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([+-−])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)/i;
const isAngle = (t) => RE_NUM.test(t) || RE_SEXA.test(t);
function raOf(t) {
  if (RE_NUM.test(t)) return +t;
  const p = t.split(/[:hms]/i).filter(Boolean).map(Number);
  return 15 * (p[0] + (p[1] || 0) / 60 + (p[2] || 0) / 3600);
}
function decOf(t) {
  if (RE_NUM.test(t)) return +t;
  const neg = /^-/.test(t.trim());
  const p = t.replace(/^[+-]/, "").split(/[:d°m'′s"″]/i).filter(Boolean).map(Number);
  const v = p[0] + (p[1] || 0) / 60 + (p[2] || 0) / 3600;
  return neg ? -v : v;
}

/** Parse one input line into {ra, dec, label} or {name} (or null for blank/comment lines). */
function parseLine(raw) {
  const line = raw.trim();
  if (!line || line.startsWith("#")) return null;
  const j = line.match(RE_JNAME);
  if (j) {
    const ra = 15 * (+j[1] + +j[2] / 60 + +j[3] / 3600);
    const dec = (j[4] === "+" ? 1 : -1) * (+j[5] + +j[6] / 60 + +j[7] / 3600);
    const label = line.replace(j[0], "").replace(/^[\s,;]+|[\s,;]+$/g, "");
    return { raw: line, ra, dec, label: label || line };
  }
  const tok = line.replace(/[,;\t]+/g, " ").trim().split(/\s+/);
  for (let i = 0; i < tok.length; i++) {
    // "hh mm ss.s ±dd mm ss.s"
    if (i + 5 < tok.length && tok.slice(i, i + 6).every((t) => RE_NUM.test(t)) &&
        Number.isInteger(+tok[i]) && +tok[i + 1] < 60 && +tok[i + 2] < 60 && +tok[i + 4] < 60 && +tok[i + 5] < 60 &&
        Number.isInteger(+tok[i + 1]) && Number.isInteger(+tok[i + 4])) {
      const ra = 15 * (+tok[i] + +tok[i + 1] / 60 + +tok[i + 2] / 3600);
      const neg = tok[i + 3].startsWith("-");
      const dec = (neg ? -1 : 1) * (Math.abs(+tok[i + 3]) + +tok[i + 4] / 60 + +tok[i + 5] / 3600);
      const label = tok.slice(0, i).concat(tok.slice(i + 6)).join(" ");
      if (ra >= 0 && ra < 360 && Math.abs(dec) <= 90) return { raw: line, ra, dec, label };
    }
    if (i + 1 < tok.length && isAngle(tok[i]) && isAngle(tok[i + 1])) {
      const ra = raOf(tok[i]), dec = decOf(tok[i + 1]);
      const label = tok.slice(0, i).concat(tok.slice(i + 2)).join(" ");
      if (ra >= 0 && ra < 360 && Math.abs(dec) <= 90) return { raw: line, ra, dec, label };
      return { raw: line, error: "Coordinates out of range (RA 0–360°, Dec −90–90°)." };
    }
  }
  return { raw: line, name: line };
}

/* ---------- data ---------- */
function paperDate(p) {
  const m = String(p.arxiv || "").match(/^(\d{2})(\d{2})\./);
  return m ? `20${m[1]}-${m[2]}` : `${p.year}-01`;
}
function paperHref(p) {
  if (p.ads_bibcode) return `https://ui.adsabs.harvard.edu/abs/${encodeURIComponent(p.ads_bibcode)}/abstract`;
  if (p.arxiv) return `https://arxiv.org/abs/${p.arxiv}`;
  if (p.doi) return `https://doi.org/${p.doi}`;
  return null;
}
function labelPapers(papers) {
  const base = (p) => p.label || `${String(p.first_author).split(" (")[0]}+${String(p.year).slice(-2)}`;
  const groups = {};
  papers.forEach((p) => (groups[base(p)] ||= []).push(p));
  Object.entries(groups).forEach(([b, list]) => {
    if (list.length === 1) { list[0]._label = b; return; }
    list.sort((x, y) => paperDate(x).localeCompare(paperDate(y)) || x.key.localeCompare(y.key))
      .forEach((p, i) => (p._label = b + "abcdefghijklmnop"[i]));
  });
}
function classOf(o) {
  if (o.lrd && o.lrd_contested) return "contested";
  if (o.lrd) return "lrd";
  if (o.broad_line === 1) return "bl";
  if (o.entries.some((e) => e.lrd === "0")) return "other";
  return "unclassified";
}
const CLASS_LABEL = { lrd: "LRD", contested: "Contested", bl: "BL AGN", other: "Not LRD", unclassified: "Unclassified" };
const CLASS_PILL = { lrd: "pill-lrd", contested: "pill-warn", bl: "pill-bl", other: "pill-plain", unclassified: "pill-plain" };
const CLASS_ORDER = { lrd: 0, contested: 1, bl: 2, other: 3, unclassified: 4 };
const ZT = ["spec", "grism", "phot"];

function prepare(data) {
  state.meta = data.meta;
  state.papers = data.papers;
  labelPapers(state.papers);
  state.papers.forEach((p) => { p._date = paperDate(p); state.paperByKey[p.key] = p; });
  state.objects = data.objects.map((o, i) => {
    o._i = i;
    o._cls = classOf(o);
    let first = null;
    o.entries.forEach((e) => {
      const p = state.paperByKey[e.paper];
      if (!first || p._date < first._date) first = p;
    });
    o._first = first;
    o._short = o.name.replace(/^LRDZ /, "");
    o._search = norm([o.name, o.field, ...o.entries.map((e) => `${e.id} ${state.paperByKey[e.paper]._label} ${e.paper}`)].join(" "));
    return o;
  });
  state.byDec = state.objects.slice().sort((a, b) => a.dec - b.dec);
}

/* ---------- cross-match ---------- */
function lowerBound(arr, dec) {
  let lo = 0, hi = arr.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (arr[mid].dec < dec) lo = mid + 1; else hi = mid; }
  return lo;
}
function coneSearch(ra, dec, radiusArcsec) {
  const r = radiusArcsec / 3600, out = [];
  for (let i = lowerBound(state.byDec, dec - r); i < state.byDec.length && state.byDec[i].dec <= dec + r; i++) {
    const o = state.byDec[i], s = sepArcsec(ra, dec, o.ra, o.dec);
    if (s <= radiusArcsec) out.push({ o, sep: s });
  }
  return out.sort((a, b) => a.sep - b.sep);
}
function runQuery() {
  const radius = +$("#q-radius").value;
  const lines = $("#q-text").value.split(/\r?\n/);
  const results = [];
  for (const raw of lines) {
    const q = parseLine(raw);
    if (!q) continue;
    if (q.error) { results.push({ q, kind: "error" }); continue; }
    if (q.name !== undefined) {
      const n = norm(q.name);
      const hits = n.length >= 3 ? state.objects.filter((o) => o._search.includes(n)).slice(0, 8) : [];
      results.push({ q, kind: "name", hits });
      continue;
    }
    const hits = coneSearch(q.ra, q.dec, radius);
    const near = hits.length ? null : coneSearch(q.ra, q.dec, 60)[0] || null;
    results.push({ q, kind: "pos", hits, near });
  }
  state.lastQuery = results;
  renderQuery(results, radius);
}
function refChip(key) {
  const p = state.paperByKey[key];
  if (!p) return "";
  const href = paperHref(p);
  return href ? `<a class="ref" href="${esc(href)}" target="_blank" rel="noopener">${esc(p._label)}</a>` : `<span class="ref">${esc(p._label)}</span>`;
}
function refChips(o, max = 4) {
  const keys = [...new Set(o.entries.map((e) => e.paper))];
  keys.sort((a, b) => state.paperByKey[a]._date.localeCompare(state.paperByKey[b]._date));
  const shown = keys.slice(0, max).map(refChip).join("");
  return `<span class="refs">${shown}${keys.length > max ? `<span class="ref">+${keys.length - max}</span>` : ""}</span>`;
}
function zCell(o) {
  if (o.z == null) return `<span class="muted">–</span>`;
  const zt = ZT.includes(o.z_type) ? o.z_type : "none";
  const digits = o.z_type === "phot" ? 2 : 3;
  return `${o.z.toFixed(digits)} <span class="ztype" title="${esc(o.z_type || "unknown")} redshift"><i class="swatch sw-${zt}"></i></span>`;
}
const classPill = (o) => `<span class="pill ${CLASS_PILL[o._cls]}">${CLASS_LABEL[o._cls]}</span>`;

function renderQuery(results, radius) {
  const box = $("#q-results");
  if (!results.length) {
    box.innerHTML = `<div class="q-empty">Paste positions on the left and press Search. Results list every published object within the match radius, with the papers that reported it.</div>`;
    return;
  }
  const pos = results.filter((r) => r.kind === "pos");
  const matched = pos.filter((r) => r.hits.length);
  const rows = results.map((r, idx) => {
    const q = r.q;
    const input = q.ra !== undefined
      ? `<span class="mono">${q.ra.toFixed(5)} ${q.dec >= 0 ? "+" : ""}${q.dec.toFixed(5)}</span>${q.label ? `<br><span class="muted">${esc(q.label)}</span>` : ""}`
      : `<span>${esc(q.raw)}</span>`;
    if (r.kind === "error") return `<tr><td>${input}</td><td colspan="4" class="muted">${esc(q.error)}</td></tr>`;
    if (r.kind === "name") {
      if (!r.hits.length) return `<tr><td>${input}</td><td colspan="4" class="muted">No object with this name or alias.</td></tr>`;
      return r.hits.map((o, k) => `<tr class="clickable" tabindex="0" data-i="${o._i}">
        <td>${k === 0 ? input : ""}</td><td><span class="mono">${esc(o._short)}</span><br>${classPill(o)}</td><td class="num muted">name</td>
        <td class="num">${zCell(o)}</td><td class="refs-cell">${refChips(o, 3)}</td></tr>`).join("");
    }
    if (!r.hits.length) {
      const near = r.near ? `Nearest published object: ${esc(r.near.o._short)}, ${r.near.sep.toFixed(1)}″ away.` : "Nothing published within 1′.";
      return `<tr><td>${input}</td><td colspan="4"><span class="pill pill-new">Not in the zoo</span> <span class="muted small">${near}</span></td></tr>`;
    }
    return r.hits.map((h, k) => `<tr class="clickable" tabindex="0" data-i="${h.o._i}">
      <td>${k === 0 ? input : ""}</td><td><span class="mono">${esc(h.o._short)}</span><br>${classPill(h.o)}</td><td class="num">${h.sep.toFixed(2)}</td>
      <td class="num">${zCell(h.o)}</td><td class="refs-cell">${refChips(h.o, 3)}</td></tr>`).join("");
  }).join("");
  const summary = pos.length
    ? `<span class="${matched.length ? "yes" : ""}">${matched.length} of ${pos.length}</span> position${pos.length > 1 ? "s" : ""} match a published object within ${radius}″.`
    : `Name search`;
  box.innerHTML = `<p class="q-summary">${summary}</p>
    <div class="table-scroll"><table class="data"><thead><tr><th>Input</th><th>Zoo object</th><th class="num">Sep (″)</th><th class="num">z</th><th>Reported in</th></tr></thead>
    <tbody>${rows}</tbody></table></div>
    <div class="q-actions"><button type="button" class="ghost-btn" id="q-csv">Download results (CSV)</button></div>`;
}
function queryCSV() {
  const out = [["input", "input_ra", "input_dec", "label", "matched", "zoo_name", "sep_arcsec", "z", "z_type", "class", "n_papers", "papers"]];
  for (const r of state.lastQuery) {
    const q = r.q;
    const base = [q.raw, q.ra?.toFixed(6) ?? "", q.dec?.toFixed(6) ?? "", q.label ?? ""];
    const hits = r.kind === "pos" ? r.hits : r.kind === "name" ? r.hits.map((o) => ({ o, sep: null })) : [];
    if (!hits.length) { out.push([...base, 0, "", "", "", "", "", "", ""]); continue; }
    for (const h of hits) {
      const o = h.o;
      out.push([...base, 1, o.name, h.sep == null ? "" : h.sep.toFixed(3), o.z ?? "", o.z_type, CLASS_LABEL[o._cls], o.n_papers,
        [...new Set(o.entries.map((e) => state.paperByKey[e.paper]._label))].join("; ")]);
    }
  }
  download("lrdzoo_crossmatch.csv", toCSV(out));
}

/* ---------- catalogue ---------- */
function readFilters() {
  return {
    text: norm($("#f-text").value), field: $("#f-field").value, paper: $("#f-paper").value,
    zmin: $("#f-zmin").value === "" ? null : +$("#f-zmin").value,
    zmax: $("#f-zmax").value === "" ? null : +$("#f-zmax").value,
    lrd: $("#f-lrd").checked, jwst: $("#f-jwst").checked, spec: $("#f-spec").checked, bl: $("#f-bl").checked, multi: $("#f-multi").checked,
    xray: $("#f-xray").checked, variable: $("#f-var").checked, miri: $("#f-miri").checked,
  };
}
function describeFilters(f) {
  const parts = [];
  if (f.lrd) parts.push("LRDs only");
  if (f.jwst) parts.push("JWST only");
  if (f.field) parts.push(f.field);
  if (f.paper) parts.push(state.paperByKey[f.paper]?._label);
  if (f.zmin != null || f.zmax != null) parts.push(`z ${f.zmin ?? 0}–${f.zmax ?? "∞"}`);
  ["spec:with spectra", "bl:broad line", "multi:2+ papers", "xray:X-ray detected", "variable:variable", "miri:MIRI"].forEach((s) => {
    const [k, l] = s.split(":"); if (f[k]) parts.push(l);
  });
  if (f.text) parts.push(`matching “${$("#f-text").value.trim()}”`);
  return parts.length ? parts.join(", ") : "no filters";
}
function applyFilters() {
  const f = readFilters();
  state.filtered = state.objects.filter((o) =>
    (!f.text || o._search.includes(f.text)) &&
    (!f.field || o.field === f.field) &&
    (!f.paper || o.entries.some((e) => e.paper === f.paper)) &&
    (f.zmin == null || (o.z != null && o.z >= f.zmin)) &&
    (f.zmax == null || (o.z != null && o.z <= f.zmax)) &&
    (!f.lrd || o.lrd) && (!f.jwst || o.jwst) && (!f.spec || o.spec) && (!f.bl || o.broad_line === 1) && (!f.multi || o.n_papers > 1) &&
    (!f.xray || o.xray === "det") && (!f.variable || o.variable === 1) && (!f.miri || o.miri));
  state.page = 0;
  sortFiltered();
  renderTable();
  $("#chart-filter-note").textContent = describeFilters(f);
  state.chartsDirty = true;
  if (!$("#view-charts").hidden) renderCharts();
}
function sortFiltered() {
  const { key, dir } = state.sort;
  const val = {
    name: (o) => o.name, ra: (o) => o.ra, dec: (o) => o.dec, field: (o) => o.field,
    z: (o) => (o.z == null ? Infinity * dir : o.z), lrd: (o) => CLASS_ORDER[o._cls], n_papers: (o) => o.n_papers,
    first: (o) => o._first._date,
  }[key];
  state.filtered.sort((a, b) => {
    const va = val(a), vb = val(b);
    return (va < vb ? -1 : va > vb ? 1 : a.ra - b.ra) * dir;
  });
  $$("#cat-table th[data-sort]").forEach((th) => {
    th.setAttribute("aria-sort", th.dataset.sort === key ? (dir > 0 ? "ascending" : "descending") : "none");
  });
}
function flagsCell(o) {
  const f = [];
  if (o.spec) f.push(`<span class="flag" title="Has a published spectrum">SPEC</span>`);
  if (o.broad_line === 1) f.push(`<span class="flag" title="Broad Balmer line reported">BL</span>`);
  else if (o.broad_line === 0) f.push(`<span class="flag neg" title="Spectrum shows no broad line">BL</span>`);
  if (o.xray === "det") f.push(`<span class="flag" title="X-ray detected">X-RAY</span>`);
  else if (o.xray === "nondet") f.push(`<span class="flag neg" title="X-ray: observed, not detected">X-RAY</span>`);
  if (o.variable === 1) f.push(`<span class="flag" title="Variability reported">VAR</span>`);
  else if (o.variable === 0) f.push(`<span class="flag neg" title="Tested for variability, not variable">VAR</span>`);
  if (o.miri) f.push(`<span class="flag" title="Appears in a MIRI study">MIRI</span>`);
  return `<span class="flags">${f.join("")}</span>`;
}
function renderTable() {
  const n = state.filtered.length, size = CONFIG.pageSize;
  const pages = Math.max(1, Math.ceil(n / size));
  state.page = Math.min(state.page, pages - 1);
  const slice = state.filtered.slice(state.page * size, (state.page + 1) * size);
  $("#cat-table tbody").innerHTML = slice.map((o) => `<tr class="clickable" tabindex="0" data-i="${o._i}">
    <td class="mono">${esc(o._short)}</td>
    <td class="num mono">${o.ra.toFixed(5)}</td>
    <td class="num mono">${o.dec >= 0 ? "+" : ""}${o.dec.toFixed(5)}</td>
    <td>${esc(o.field)}</td>
    <td class="num">${zCell(o)}</td>
    <td>${classPill(o)}</td>
    <td>${flagsCell(o)}</td>
    <td class="num">${o.n_papers}</td>
    <td>${refChip(o._first.key)}</td></tr>`).join("") ||
    `<tr><td colspan="9" class="muted">No objects match these filters.</td></tr>`;
  $("#cat-count").innerHTML = `Showing <b>${fmtInt(n)}</b> of ${fmtInt(state.objects.length)} objects. Dashed flags mean tested and not found.`;
  $("#cat-pager").innerHTML = pages > 1
    ? `<button type="button" class="ghost-btn" data-page="prev" ${state.page === 0 ? "disabled" : ""}>Previous</button>
       <span>Page ${state.page + 1} of ${pages}</span>
       <button type="button" class="ghost-btn" data-page="next" ${state.page >= pages - 1 ? "disabled" : ""}>Next</button>`
    : "";
}
function catalogueCSV() {
  const rows = [["name", "ra", "dec", "field", "z", "z_type", "z_ref", "class", "spec", "broad_line", "xray", "variable", "miri",
    "f444w", "n_papers", "first_reported", "papers", "aliases"]];
  state.filtered.forEach((o) => rows.push([o.name, o.ra, o.dec, o.field, o.z ?? "", o.z_type, o.z_ref, CLASS_LABEL[o._cls],
    +o.spec, o.broad_line ?? "", o.xray ?? "", o.variable ?? "", +o.miri, o.f444w ?? "", o.n_papers, o._first._label,
    [...new Set(o.entries.map((e) => state.paperByKey[e.paper]._label))].join("; "), o.entries.map((e) => e.id).join("; ")]));
  download("lrdzoo_selection.csv", toCSV(rows));
}

/* ---------- detail drawer ---------- */
function cutoutFor(o) {
  const jwst = o.field !== "Other" && !(o.z != null && o.z < 1);
  if (jwst) {
    const q = `coord=${o.ra.toFixed(6)},${o.dec.toFixed(6)}&size=3&filters=f115w-clear,f277w-clear,f444w-clear`;
    return { src: `https://grizli-cutout.herokuapp.com/thumb?${q}`, cap: "DJA NIRCam F115W/F277W/F444W, 3″", href: `https://grizli-cutout.herokuapp.com/thumb?${q}` };
  }
  return {
    src: `https://www.legacysurvey.org/viewer/cutout.jpg?ra=${o.ra.toFixed(6)}&dec=${o.dec.toFixed(6)}&layer=ls-dr10&pixscale=0.262&size=96`,
    cap: "Legacy Surveys DR10, 25″",
    href: `https://www.legacysurvey.org/viewer?ra=${o.ra.toFixed(6)}&dec=${o.dec.toFixed(6)}&layer=ls-dr10&zoom=16`,
  };
}
function triText(v, yes, no) { return v === "1" ? yes : v === "0" ? no : ""; }
function openDetail(o, pushHash = true) {
  const ra = o.ra.toFixed(6), dec = (o.dec >= 0 ? "+" : "") + o.dec.toFixed(6);
  const cut = cutoutFor(o);
  const keys = [...new Set(o.entries.map((e) => e.paper))];
  const zref = state.paperByKey[o.z_ref];
  const entries = o.entries.slice().sort((a, b) => state.paperByKey[a.paper]._date.localeCompare(state.paperByKey[b.paper]._date));
  const notes = entries.filter((e) => e.notes || e.corrected).map((e) => `<li><b>${esc(state.paperByKey[e.paper]._label)}${e.corrected ? " (corrected)" : ""}:</b> ${esc([e.corrected, e.notes].filter(Boolean).join(" · "))}</li>`).join("");
  $("#d-title").textContent = o.name;
  $("#d-body").innerHTML = `
    <div class="d-grid">
      <dl class="kv">
        <dt>RA, Dec</dt><dd class="mono">${ra} ${dec}</dd>
        <dt></dt><dd class="mono">${fmtRA(o.ra)} ${fmtDec(o.dec)}</dd>
        <dt>Field</dt><dd>${esc(o.field)}</dd>
        <dt>Redshift</dt><dd>${o.z != null ? `${zCell(o)} <span class="muted">${esc(o.z_type)}${zref ? `, ${esc(zref._label)}` : ""}</span>` : `<span class="muted">none given</span>`}</dd>
        <dt>Class</dt><dd>${classPill(o)}</dd>
        <dt>Data</dt><dd>${flagsCell(o) || "–"}</dd>
        ${o.f444w != null ? `<dt>F444W</dt><dd>${o.f444w.toFixed(2)} AB</dd>` : ""}
        <dt>First reported</dt><dd>${refChip(o._first.key)} <span class="muted">${esc(o._first._date)}</span></dd>
        <dt>Position spread</dt><dd>${o.max_sep.toFixed(2)}″ <span class="muted">(largest offset of a paper's position from the mean)</span></dd>
      </dl>
      <div>
        <a class="cutout" href="${esc(cut.href)}" target="_blank" rel="noopener"><img src="${esc(cut.src)}" alt="Image cutout around ${esc(o._short)}" loading="lazy"></a>
        <p class="cutout-cap">${esc(cut.cap)}</p>
      </div>
    </div>
    <div class="copy-row">
      <button type="button" class="ghost-btn" data-copy="${esc(o.name)}">Copy name</button>
      <button type="button" class="ghost-btn" data-copy="${ra} ${dec}">Copy RA Dec</button>
      <button type="button" class="ghost-btn" data-copy-bib="${o._i}">Copy BibTeX (${keys.length} paper${keys.length > 1 ? "s" : ""})</button>
      <button type="button" class="ghost-btn" data-copy="${esc(location.origin + location.pathname)}#${esc(o._short)}">Copy link</button>
    </div>
    <div class="d-section">
      <h3>Reported in ${keys.length} paper${keys.length > 1 ? "s" : ""}</h3>
      <div class="table-scroll"><table class="data">
        <thead><tr><th>Paper</th><th>ID in paper</th><th class="num">z</th><th>LRD</th><th>Data</th><th class="num">Offset (″)</th></tr></thead>
        <tbody>${entries.map((e) => {
          const bits = [e.spec, triText(e.broad_line, "broad line", "no broad line"), e.xray === "det" ? "X-ray det." : e.xray === "nondet" ? "X-ray non-det." : "",
            triText(e.variable, "variable", "not variable")].filter(Boolean).join(", ");
          return `<tr><td>${refChip(e.paper)}${e.corrected ? ` <span class="pill pill-warn" title="${esc(e.corrected)}">corrected</span>` : ""}</td><td class="mono">${esc(e.id)}</td>
            <td class="num">${e.z != null ? `${(+e.z).toFixed(e.z_type === "phot" ? 2 : 3)} <span class="muted">${esc(e.z_type)}</span>` : "–"}</td>
            <td>${e.lrd === "1" ? "yes" : e.lrd === "0" ? "no" : ""}</td><td>${esc(bits)}</td><td class="num">${e.sep.toFixed(2)}</td></tr>`;
        }).join("")}</tbody></table></div>
      ${notes ? `<ul class="small">${notes}</ul>` : ""}
    </div>
    <div class="d-section">
      <h3>Look it up elsewhere</h3>
      <div class="d-links">
        <a class="ghost-btn" target="_blank" rel="noopener" href="https://grizli-cutout.herokuapp.com/thumb?coord=${o.ra.toFixed(6)},${o.dec.toFixed(6)}&size=6&filters=f115w-clear,f150w-clear,f200w-clear,f277w-clear,f356w-clear,f444w-clear&all_filters=True">DJA all-filter cutout</a>
        <a class="ghost-btn" target="_blank" rel="noopener" href="https://simbad.cds.unistra.fr/simbad/sim-coo?Coord=${o.ra.toFixed(6)}%20${o.dec.toFixed(6)}&Radius=2&Radius.unit=arcsec">SIMBAD</a>
        <a class="ghost-btn" target="_blank" rel="noopener" href="https://vizier.cds.unistra.fr/viz-bin/VizieR?-c=${o.ra.toFixed(6)}%20${o.dec.toFixed(6)}&-c.rs=2">VizieR (2″)</a>
        <a class="ghost-btn" target="_blank" rel="noopener" href="https://sky.esa.int/esasky/?target=${o.ra.toFixed(6)}%20${o.dec.toFixed(6)}&fov=0.01&sci=true">ESASky</a>
        <a class="ghost-btn" target="_blank" rel="noopener" href="https://www.legacysurvey.org/viewer?ra=${o.ra.toFixed(6)}&dec=${o.dec.toFixed(6)}&layer=ls-dr10&zoom=16">Legacy Surveys</a>
      </div>
    </div>`;
  const img = $("#d-body .cutout img");
  img.addEventListener("error", () => { img.replaceWith(Object.assign(document.createElement("span"), { textContent: "No cutout available here" })); });
  $("#drawer").hidden = false;
  $("#d-close").focus({ preventScroll: true });
  if (pushHash) history.replaceState(null, "", `#${o._short}`);
}
function closeDetail() {
  $("#drawer").hidden = true;
  const tab = $$(".tabs [role=tab]").find((t) => t.getAttribute("aria-selected") === "true");
  history.replaceState(null, "", `#${tab.id.replace("tab-", "")}`);
}
function bibFor(o) {
  return [...new Set(o.entries.map((e) => e.paper))].map((k) => state.paperByKey[k].bibtex).join("\n");
}

/* ---------- charts ---------- */
const NS = "http://www.w3.org/2000/svg";
function niceStep(range, target) {
  const raw = range / target, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
}
function ticks(lo, hi, target) {
  const step = niceStep(hi - lo || 1, target), out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return { out, step };
}
const tip = $("#tooltip");
function showTip(html, ev) {
  tip.innerHTML = html;
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + w > window.innerWidth - 8) x = ev.clientX - w - 14;
  if (y + h > window.innerHeight - 8) y = ev.clientY - h - 14;
  tip.style.left = `${Math.max(8, x)}px`;
  tip.style.top = `${Math.max(8, y)}px`;
}
const hideTip = () => { tip.hidden = true; };
function svgPoint(svg, ev) {
  const pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}
const ztClass = (o) => (ZT.includes(o.z_type) ? o.z_type : "none");
function objTip(o) {
  return `<b>${esc(o._short)}</b><br>${esc(o.field)} · ${o.z != null ? `z = ${o.z.toFixed(o.z_type === "phot" ? 2 : 3)} (${esc(o.z_type)})` : "no z"}<br>${CLASS_LABEL[o._cls]} · ${o.n_papers} paper${o.n_papers > 1 ? "s" : ""}`;
}
/** Attach nearest-point hover + click to an SVG whose points are [{x, y, o}]. */
function bindScatter(svg, pts, onTip, onClick, maxDist = 10) {
  const ring = document.createElementNS(NS, "circle");
  ring.setAttribute("class", "hover-ring"); ring.setAttribute("r", "6"); ring.style.display = "none";
  svg.appendChild(ring);
  const scale = () => svg.viewBox.baseVal.width / svg.getBoundingClientRect().width;
  let current = null;
  svg.addEventListener("pointermove", (ev) => {
    const p = svgPoint(svg, ev), lim = maxDist * scale();
    let best = null, bd = lim * lim;
    for (const q of pts) { const d = (q.x - p.x) ** 2 + (q.y - p.y) ** 2; if (d < bd) { bd = d; best = q; } }
    current = best;
    if (!best) { ring.style.display = "none"; hideTip(); svg.style.cursor = ""; return; }
    ring.setAttribute("cx", best.x); ring.setAttribute("cy", best.y); ring.style.display = "";
    svg.style.cursor = "pointer";
    showTip(onTip(best), ev);
  });
  svg.addEventListener("pointerleave", () => { ring.style.display = "none"; hideTip(); current = null; });
  svg.addEventListener("click", () => { if (current) onClick(current); });
}
/** Draw charts at the container's real width so 11px labels stay 11px on phones. */
function chartWidth(box, preferred) {
  const w = box.clientWidth;
  return w ? Math.round(Math.max(320, Math.min(preferred, w))) : preferred;
}
function hammer(ra, dec) {
  const l = (180 - ra) * D2R, b = dec * D2R;
  const d = Math.sqrt(1 + Math.cos(b) * Math.cos(l / 2));
  return [(2 * Math.SQRT2 * Math.cos(b) * Math.sin(l / 2)) / d, (Math.SQRT2 * Math.sin(b)) / d];
}
function renderSkyAll(objs) {
  const box = $("#sky-all");
  const W = chartWidth(box, 960), H = Math.round(W * 0.52), cx = W / 2, cy = H / 2, s = (W / 2 - 20) / (2 * Math.SQRT2);
  const P = (ra, dec) => { const [x, y] = hammer(ra, dec); return [cx + x * s, cy - y * s]; };
  let g = `<ellipse class="sky-outline" cx="${cx}" cy="${cy}" rx="${2 * Math.SQRT2 * s}" ry="${Math.SQRT2 * s}"/>`;
  for (const dec of [-60, -30, 0, 30, 60]) {
    const pts = []; for (let ra = 0; ra <= 360; ra += 5) pts.push(P(ra === 360 ? 359.999 : ra, dec).map((v) => v.toFixed(1)).join(","));
    g += `<polyline class="grid-line" fill="none" points="${pts.join(" ")}"/>`;
    if (dec) { const [x, y] = P(180, dec); g += `<text x="${x + 4}" y="${y - 3}">${dec > 0 ? "+" : "−"}${Math.abs(dec)}°</text>`; }
  }
  for (let ra = 0; ra < 360; ra += 60) {
    if (ra === 0) continue;
    const pts = []; for (let dec = -90; dec <= 90; dec += 5) pts.push(P(ra, dec).map((v) => v.toFixed(1)).join(","));
    g += `<polyline class="grid-line" fill="none" points="${pts.join(" ")}"/>`;
    const [x, y] = P(ra, 0); g += `<text x="${x + 3}" y="${y + 13}">${ra / 15}h</text>`;
  }
  const pts = objs.map((o) => { const [x, y] = P(o.ra, o.dec); return { x, y, o }; });
  g += pts.map((p) => `<circle class="pt pt-${ztClass(p.o)}" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.6"/>`).join("");
  // field labels
  const byField = {};
  objs.forEach((o) => { if (o.field !== "Other") (byField[o.field] ||= []).push(o); });
  // label the ten most populated fields; the rest are still named on hover
  const labels = Object.entries(byField).filter(([, list]) => list.length >= 10)
    .sort((a, b) => b[1].length - a[1].length).slice(0, 10)
    .map(([f, list]) => { const [x, y] = P(list[0].ra, list[0].dec); return { f, n: list.length, x, y }; })
    .sort((a, b) => a.y - b.y);
  const placed = [];
  for (const L of labels) {
    const text = `${L.f} ${fmtInt(L.n)}`, w = text.length * 6.4;
    let lx = L.x + 8, ly = L.y - 6;
    if (lx + w > W - 4) lx = L.x - 8 - w;
    while (placed.some((p) => Math.abs(p.y - ly) < 13 && lx < p.x + p.w && lx + w > p.x)) ly += 13;
    placed.push({ x: lx, y: ly, w });
    g += `<text class="field-label" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}">${esc(text)}</text>`;
  }
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="All-sky map (Hammer projection, equatorial) of ${objs.length} objects">${g}</svg>`;
  bindScatter($("svg", box), pts, (p) => (p.o.field !== "Other" ? `<b>${esc(p.o.field)}</b><br>${fmtInt(byField[p.o.field].length)} objects · click to see the field` : objTip(p.o)),
    (p) => {
      if (p.o.field === "Other") return openDetail(p.o);
      const panel = document.getElementById(`panel-${slug(p.o.field)}`);
      if (panel) panel.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 8);
}
function renderFields(objs) {
  const byField = {};
  objs.forEach((o) => { if (o.field !== "Other") (byField[o.field] ||= []).push(o); });
  const fields = Object.entries(byField).filter(([, l]) => l.length >= 2).sort((a, b) => b[1].length - a[1].length);
  const box = $("#sky-fields");
  if (!fields.length) { box.innerHTML = `<p class="muted">No deep-field objects pass the current filters.</p>`; return; }
  box.innerHTML = fields.map(([f, list]) => `<div class="panel" id="panel-${slug(f)}"><h4>${esc(f)} <span>${fmtInt(list.length)}</span></h4><div class="panel-svg"></div></div>`).join("");
  fields.forEach(([f, list]) => {
    const W = 300, H = 300, m = { l: 40, r: 10, t: 8, b: 30 };
    const dec0 = list.reduce((s, o) => s + o.dec, 0) / list.length;
    let ra0 = list[0].ra; // handle RA wrap at 0
    const unwrap = (ra) => { let d = ra - ra0; if (d > 180) d -= 360; if (d < -180) d += 360; return ra0 + d; };
    const ras = list.map((o) => unwrap(o.ra));
    ra0 = ras.reduce((a, b) => a + b, 0) / ras.length;
    const c = Math.cos(dec0 * D2R);
    const xs = ras.map((ra) => -(ra - ra0) * c), ys = list.map((o) => o.dec - dec0);
    const half = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1 / 60) * 0.55;
    const xm = (Math.max(...xs) + Math.min(...xs)) / 2, ym = (Math.max(...ys) + Math.min(...ys)) / 2;
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    const X = (x) => m.l + ((x - (xm - half)) / (2 * half)) * pw;
    const Y = (y) => m.t + ph - ((y - (ym - half)) / (2 * half)) * ph;
    let g = `<rect class="frame" x="${m.l}" y="${m.t}" width="${pw}" height="${ph}"/>`;
    // RA ticks (degrees), mapped through the tangent-plane x
    const raLo = ra0 - (xm + half) / c, raHi = ra0 - (xm - half) / c;
    const rt = ticks(raLo, raHi, 4), rdig = Math.max(0, -Math.floor(Math.log10(rt.step)));
    rt.out.forEach((ra) => {
      const x = X(-(ra - ra0) * c);
      if (x < m.l + 1 || x > m.l + pw - 1) return;
      g += `<line class="grid-line" x1="${x}" x2="${x}" y1="${m.t}" y2="${m.t + ph}"/><text x="${x}" y="${H - 14}" text-anchor="middle">${(((ra % 360) + 360) % 360).toFixed(rdig)}</text>`;
    });
    const dt = ticks(dec0 + ym - half, dec0 + ym + half, 4), ddig = Math.max(0, -Math.floor(Math.log10(dt.step)));
    dt.out.forEach((d) => {
      const y = Y(d - dec0);
      if (y < m.t + 1 || y > m.t + ph - 1) return;
      g += `<line class="grid-line" x1="${m.l}" x2="${m.l + pw}" y1="${y}" y2="${y}"/><text x="${m.l - 5}" y="${y + 4}" text-anchor="end">${d.toFixed(ddig)}</text>`;
    });
    g += `<text x="${m.l + pw / 2}" y="${H - 1}" text-anchor="middle">RA (deg)</text>`;
    g += `<text x="10" y="${m.t + ph / 2}" text-anchor="middle" transform="rotate(-90 10 ${m.t + ph / 2})">Dec (deg)</text>`;
    // 1-arcmin scale bar
    const bar = (1 / 60) / (2 * half) * pw;
    if (bar > 8 && bar < pw * 0.6) g += `<line class="axis-line" x1="${m.l + pw - 8 - bar}" x2="${m.l + pw - 8}" y1="${m.t + ph - 10}" y2="${m.t + ph - 10}" stroke-width="2"/><text x="${m.l + pw - 8 - bar / 2}" y="${m.t + ph - 14}" text-anchor="middle">1′</text>`;
    const pts = list.map((o, k) => ({ x: X(xs[k]), y: Y(ys[k]), o }));
    g += pts.map((p) => `<circle class="pt pt-${ztClass(p.o)}" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3"/>`).join("");
    const holder = $(".panel-svg", document.getElementById(`panel-${slug(f)}`));
    holder.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(f)}: ${list.length} objects">${g}</svg>`;
    bindScatter($("svg", holder), pts, (p) => objTip(p.o), (p) => openDetail(p.o));
  });
}
function renderZHist(objs) {
  const withZ = objs.filter((o) => o.z != null);
  const box = $("#z-hist");
  if (!withZ.length) { box.innerHTML = `<p class="muted">No redshifts among the filtered objects.</p>`; return; }
  const bw = 0.25, zmax = Math.ceil(Math.max(...withZ.map((o) => o.z)) + 1e-9), zmin = Math.floor(Math.min(...withZ.map((o) => o.z)));
  const nb = Math.round((zmax - zmin) / bw);
  const bins = Array.from({ length: nb }, () => ({ spec: 0, grism: 0, phot: 0 }));
  withZ.forEach((o) => { const k = Math.min(nb - 1, Math.floor((o.z - zmin) / bw)); bins[k][ZT.includes(o.z_type) ? o.z_type : "phot"] += 1; });
  const tot = bins.map((b) => b.spec + b.grism + b.phot), ymax = Math.max(...tot);
  const W = chartWidth(box, 640), H = 290, m = { l: 44, r: 8, t: 10, b: 34 }, pw = W - m.l - m.r, ph = H - m.t - m.b;
  const yt = ticks(0, ymax * 1.05, 4), ytop = Math.max(yt.out[yt.out.length - 1], ymax);
  const X = (z) => m.l + ((z - zmin) / (zmax - zmin)) * pw, Y = (v) => m.t + ph - (v / ytop) * ph;
  let g = "";
  yt.out.forEach((v) => { g += `<line class="grid-line" x1="${m.l}" x2="${m.l + pw}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${fmtInt(v)}</text>`; });
  const xstep = zmax - zmin > (W < 480 ? 5 : 8) ? 2 : 1;
  for (let z = zmin; z <= zmax; z += xstep) g += `<text x="${X(z)}" y="${m.t + ph + 16}" text-anchor="middle">${z}</text>`;
  g += `<text x="${m.l + pw / 2}" y="${H - 2}" text-anchor="middle">Redshift</text>`;
  const bwPx = pw / nb;
  bins.forEach((b, k) => {
    let acc = 0;
    for (const t of ZT) {
      if (!b[t]) continue;
      const y0 = Y(acc), y1 = Y(acc + b[t]);
      g += `<rect class="bar-${t} bar-gap" x="${(m.l + k * bwPx + 0.5).toFixed(1)}" y="${y1.toFixed(1)}" width="${Math.max(1, bwPx - 1).toFixed(1)}" height="${(y0 - y1).toFixed(1)}"/>`;
      acc += b[t];
    }
  });
  g += `<line class="axis-line" x1="${m.l}" x2="${m.l + pw}" y1="${m.t + ph}" y2="${m.t + ph}"/>`;
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Histogram of adopted redshifts, ${withZ.length} objects">${g}<rect id="zh-hl" fill="var(--ink)" opacity="0.06" y="${m.t}" height="${ph}" width="${bwPx}" style="display:none"/></svg>
    <p class="muted small">${fmtInt(withZ.length)} objects with a redshift${objs.length > withZ.length ? `; ${fmtInt(objs.length - withZ.length)} without` : ""}. Bins of Δz = ${bw}.</p>`;
  const svg = $("svg", box), hl = $("#zh-hl", box);
  svg.addEventListener("pointermove", (ev) => {
    const p = svgPoint(svg, ev), k = Math.floor((p.x - m.l) / bwPx);
    if (k < 0 || k >= nb || p.y < m.t || p.y > m.t + ph) { hl.style.display = "none"; hideTip(); return; }
    const b = bins[k];
    hl.setAttribute("x", m.l + k * bwPx); hl.style.display = "";
    showTip(`<b>z ${(zmin + k * bw).toFixed(2)}–${(zmin + (k + 1) * bw).toFixed(2)}: ${fmtInt(tot[k])}</b><br>spec ${b.spec} · grism ${b.grism} · phot ${b.phot}`, ev);
  });
  svg.addEventListener("pointerleave", () => { hl.style.display = "none"; hideTip(); });
}
function renderGrowth(objs) {
  const box = $("#growth");
  if (!objs.length) { box.innerHTML = ""; return; }
  const months = (s) => { const [y, mo] = s.split("-").map(Number); return y * 12 + mo - 1; };
  const label = (i) => `${Math.floor(i / 12)}-${pad2((i % 12) + 1)}`;
  const counts = {}, byPaper = {};
  objs.forEach((o) => {
    const k = months(o._first._date);
    counts[k] = (counts[k] || 0) + 1;
    ((byPaper[k] ||= {})[o._first.key] = (byPaper[k][o._first.key] || 0) + 1);
  });
  const m0 = Math.min(...Object.keys(counts).map(Number)) - 1;
  const m1 = Math.max(months(new Date().toISOString().slice(0, 7)), Math.max(...Object.keys(counts).map(Number)));
  const series = []; let acc = 0;
  for (let k = m0; k <= m1; k++) { acc += counts[k] || 0; series.push({ k, v: acc, add: counts[k] || 0 }); }
  const W = chartWidth(box, 640), H = 290, m = { l: 48, r: 56, t: 14, b: 34 }, pw = W - m.l - m.r, ph = H - m.t - m.b;
  const yt = ticks(0, acc * 1.05, 4), ytop = Math.max(yt.out[yt.out.length - 1], acc);
  const X = (k) => m.l + ((k - m0) / Math.max(1, m1 - m0)) * pw, Y = (v) => m.t + ph - (v / ytop) * ph;
  let g = "";
  yt.out.forEach((v) => { g += `<line class="grid-line" x1="${m.l}" x2="${m.l + pw}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${fmtInt(v)}</text>`; });
  for (let y = Math.ceil(m0 / 12); y * 12 <= m1; y++) {
    const x = X(y * 12);
    if (x >= m.l) g += `<line class="axis-line" x1="${x}" x2="${x}" y1="${m.t + ph}" y2="${m.t + ph + 4}"/><text x="${x}" y="${m.t + ph + 17}" text-anchor="middle">${y}</text>`;
  }
  let d = `M${X(series[0].k)},${Y(0)}`;
  series.forEach((s, i) => { if (i) d += `H${X(s.k)}`; d += `V${Y(s.v)}`; });
  d += `H${X(m1)}`;
  g += `<path class="growth-area" d="${d}V${Y(0)}H${X(series[0].k)}Z"/><path class="growth-line" d="${d}"/>`;
  // annotate the largest single-month additions
  const big = series.filter((s) => s.add >= Math.max(10, acc * 0.08)).sort((a, b) => b.add - a.add).slice(0, 4);
  const placed = [];
  big.sort((a, b) => a.k - b.k).forEach((s) => {
    const top = Object.entries(byPaper[s.k]).sort((a, b) => b[1] - a[1])[0][0];
    const text = state.paperByKey[top]._label, w = text.length * 6.2;
    // left of the step's riser; if there is no room, above the step's tread
    let x = X(s.k) - 5 - w, y = Y(s.v) + 4;
    if (x < m.l + 2) { x = Math.min(X(s.k) + 6, m.l + pw - w); y = Y(s.v) - 7; }
    while (placed.some((p) => Math.abs(p.y - y) < 13 && x < p.x + p.w && x + w > p.x)) y += 13;
    placed.push({ x, y, w });
    g += `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}">${esc(text)}</text>`;
  });
  g += `<circle class="end-dot" cx="${X(m1)}" cy="${Y(acc)}" r="4.5"/><text class="end-label" x="${X(m1) + 8}" y="${Y(acc) + 4}">${fmtInt(acc)}</text>`;
  g += `<line class="axis-line" x1="${m.l}" x2="${m.l + pw}" y1="${m.t + ph}" y2="${m.t + ph}"/>`;
  g += `<line id="gr-x" class="crosshair" y1="${m.t}" y2="${m.t + ph}" style="display:none"/>`;
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cumulative number of objects by the arXiv month of their first report">${g}</svg>
    <p class="muted small">Month of the arXiv submission of the first paper that lists each object. Labels name the paper behind the biggest jumps.</p>`;
  const svg = $("svg", box), cross = $("#gr-x", box);
  svg.addEventListener("pointermove", (ev) => {
    const p = svgPoint(svg, ev);
    if (p.x < m.l || p.x > m.l + pw) { cross.style.display = "none"; hideTip(); return; }
    const k = Math.round(m0 + ((p.x - m.l) / pw) * (m1 - m0)), s = series[k - m0];
    if (!s) return;
    cross.setAttribute("x1", X(k)); cross.setAttribute("x2", X(k)); cross.style.display = "";
    const who = byPaper[k] ? Object.entries(byPaper[k]).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([key, n]) => `${esc(state.paperByKey[key]._label)} +${n}`).join("<br>") : "";
    showTip(`<b>${label(k)}: ${fmtInt(s.v)} objects</b>${s.add ? `<br>${who}` : ""}`, ev);
  });
  svg.addEventListener("pointerleave", () => { cross.style.display = "none"; hideTip(); });
}
function renderCharts() {
  if (!state.chartsDirty) return;
  state.chartsDirty = false;
  const objs = state.filtered;
  renderSkyAll(objs);
  renderFields(objs);
  renderZHist(objs);
  renderGrowth(objs);
}

/* ---------- papers ---------- */
const SELECTION_LABEL = {
  photometric: "Photometric", spectroscopic: "Spectroscopic", grism: "Grism", variability: "Variability", xray: "X-ray",
  radio: "Radio", infrared: "Infrared", compilation: "Compilation", individual: "Individual object", local: "Local analogue",
};
function renderPapers() {
  const list = state.papers.slice().sort((a, b) => b._date.localeCompare(a._date) || a.key.localeCompare(b.key));
  $("#papers-table tbody").innerHTML = list.map((p) => {
    const href = paperHref(p);
    return `<tr>
      <td>${href ? `<a href="${esc(href)}" target="_blank" rel="noopener"><b>${esc(p._label)}</b></a>` : `<b>${esc(p._label)}</b>`}<br><span class="muted small">${esc(p.journal || (p.arxiv ? `arXiv:${p.arxiv}` : ""))}</span></td>
      <td class="title-cell">${esc(p.title)}</td>
      <td><span class="pill pill-plain">${esc(SELECTION_LABEL[p.selection] || p.selection)}</span></td>
      <td class="num">${fmtInt(p.n_rows)}</td>
      <td class="num">${fmtInt(p.n_lrd)}</td>
      <td class="num">${fmtInt(p.n_first)}</td>
      <td><button type="button" class="link-btn" data-show-paper="${esc(p.key)}">Show objects</button><br><a class="small" href="${esc(p.source_url)}" target="_blank" rel="noopener" title="${esc(p.source_note)}">Data source</a></td>
    </tr>`;
  }).join("");
  $("#papers-count").textContent = `${state.papers.length} papers, ${fmtInt(state.meta.n_entries)} table rows in total.`;
}

/* ---------- arXiv inbox ---------- */
const INBOX_STATUS = { todo: "To review", in_zoo: "In the zoo", ignored: "Ignored" };
function renderInbox() {
  const box = $("#inbox-list");
  if (!state.inbox) {
    $("#inbox-note").textContent = "The arXiv inbox has not been generated yet. Run scripts/arxiv_monitor.py.";
    return;
  }
  const papers = state.inbox.papers;
  const counts = { todo: 0, in_zoo: 0, ignored: 0 };
  papers.forEach((p) => (counts[p.status] = (counts[p.status] || 0) + 1));
  if (!state.inboxFilter) state.inboxFilter = counts.todo ? "todo" : "all";
  $("#inbox-note").textContent = `Papers that mention little red dots in their title or abstract, checked daily on arXiv (last check ${state.inbox.updated}). "To review" papers are not in the zoo yet; many are theory papers without an object list.`;
  $("#inbox-filter").innerHTML = [["todo", "To review"], ["in_zoo", "In the zoo"], ["ignored", "Ignored"], ["all", "All"]]
    .map(([k, l]) => `<button type="button" class="chip-btn" data-inbox="${k}" aria-pressed="${state.inboxFilter === k}">${l} <span class="muted">${k === "all" ? papers.length : counts[k] || 0}</span></button>`).join("");
  const since = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
  const recent = papers.filter((p) => p.status === "todo" && p.published >= since).length;
  const badge = $("#inbox-badge");
  badge.textContent = recent; badge.hidden = !recent;
  badge.title = `${recent} papers from the last 30 days still to review`;
  const shown = papers.filter((p) => state.inboxFilter === "all" || p.status === state.inboxFilter);
  box.innerHTML = shown.map((p) => {
    const authors = p.authors.slice(0, 3).join(", ") + (p.authors.length > 3 ? " et al." : "");
    const status = p.status === "in_zoo"
      ? `<span class="pill pill-lrd">In the zoo</span>`
      : p.status === "ignored" ? `<span class="pill pill-plain" title="${esc(p.ignore_reason || "")}">Ignored</span>` : `<span class="pill pill-new">To review</span>`;
    const hint = p.status === "todo" && p.sample_hint ? `<span class="pill pill-warn">May list a sample</span>` : "";
    return `<li><span class="date">${esc(p.published)}</span>
      <div><div class="title"><a href="https://arxiv.org/abs/${esc(p.arxiv)}" target="_blank" rel="noopener">${esc(p.title)}</a></div>
      <div class="meta">${status}${hint}<span>${esc(authors)}</span><span class="muted">arXiv:${esc(p.arxiv)} · ${esc(p.primary)}</span></div></div>
      <details><summary>Abstract</summary><p>${esc(p.abstract)}</p></details></li>`;
  }).join("") || `<li class="muted">Nothing here.</li>`;
}

/* ---------- utilities ---------- */
function toCSV(rows) {
  return rows.map((r) => r.map((v) => { const s = String(v ?? ""); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }).join(",")).join("\n") + "\n";
}
function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function copyText(text, btn) {
  const old = btn.textContent;
  try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; }
  catch { window.prompt("Copy:", text); }
  setTimeout(() => (btn.textContent = old), 1400);
}

/* ---------- tabs, theme, events ---------- */
function selectTab(name, updateHash = true) {
  $$(".tabs [role=tab]").forEach((t) => {
    const on = t.id === `tab-${name}`;
    t.setAttribute("aria-selected", on);
    $(`#${t.getAttribute("aria-controls")}`).hidden = !on;
  });
  if (name === "charts") renderCharts();
  if (updateHash) history.replaceState(null, "", `#${name}`);
}
const THEMES = ["auto", "light", "dark"];
function applyTheme(t) {
  if (t === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  $("#theme-btn").textContent = `Theme: ${t}`;
}
function initTheme() {
  let t = "auto";
  try { t = localStorage.getItem("lrdzoo-theme") || "auto"; } catch { /* storage unavailable */ }
  applyTheme(THEMES.includes(t) ? t : "auto");
  $("#theme-btn").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || "auto";
    const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
    applyTheme(next);
    try { localStorage.setItem("lrdzoo-theme", next); } catch { /* ignore */ }
  });
}
function exampleInput() {
  const pick = (re) => state.objects.find((o) => o.lrd && o.entries.some((e) => re.test(e.id)));
  const multi = state.objects.filter((o) => o.lrd && o.jwst && o.n_papers > 1).sort((a, b) => b.n_papers - a.n_papers);
  const lrds = state.objects.filter((o) => o.lrd && o.jwst);
  const a = pick(/QSO1/i) || multi[0] || lrds[0] || state.objects[0];
  const b = multi.find((o) => o !== a && o.field !== a.field) || lrds.find((o) => o !== a && o.field !== a.field) ||
    lrds.find((o) => o !== a) || a;
  const off = 0.15 / 3600 / Math.cos(a.dec * D2R);
  const lines = [
    `${(a.ra + off).toFixed(6)}  ${a.dec >= 0 ? "+" : ""}${a.dec.toFixed(6)}  my-candidate-1`,
    `${fmtRA(b.ra)} ${fmtDec(b.dec + 0.1 / 3600)}  my-candidate-2`,
  ];
  // an empty position: step away from b until nothing is within 20"
  for (let k = 1; k < 40; k++) {
    const dec = b.dec + (k * 25) / 3600;
    if (!coneSearch(b.ra, dec, 20).length) { lines.push(`${b.ra.toFixed(6)}  ${dec >= 0 ? "+" : ""}${dec.toFixed(6)}  blank-sky-test`); break; }
  }
  return lines.join("\n");
}
function fillSelects() {
  const fields = {};
  state.objects.forEach((o) => (fields[o.field] = (fields[o.field] || 0) + 1));
  $("#f-field").innerHTML += Object.entries(fields).sort((a, b) => b[1] - a[1])
    .map(([f, n]) => `<option value="${esc(f)}">${esc(f)} (${fmtInt(n)})</option>`).join("");
  $("#f-paper").innerHTML += state.papers.slice().sort((a, b) => a._label.localeCompare(b._label))
    .map((p) => `<option value="${esc(p.key)}">${esc(p._label)}</option>`).join("");
}
function bindEvents() {
  $("#q-form").addEventListener("submit", (ev) => { ev.preventDefault(); $("#q-example-note").hidden = true; runQuery(); });
  $("#q-clear").addEventListener("click", () => { $("#q-text").value = ""; $("#q-example-note").hidden = true; state.lastQuery = []; renderQuery([], 1); $("#q-text").focus(); });
  $("#q-file").addEventListener("change", async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((l) => l.trim());
    const head = lines[0].split(/[,\t;]/).map((h) => h.trim().toLowerCase());
    const iRa = head.findIndex((h) => /^(ra|raj2000|ra_deg|radeg|alpha)$/.test(h));
    const iDec = head.findIndex((h) => /^(dec|dej2000|decj2000|dec_deg|dedeg|delta)$/.test(h));
    const iName = head.findIndex((h) => /^(id|name|source|object|label)$/.test(h));
    $("#q-text").value = iRa >= 0 && iDec >= 0
      ? lines.slice(1).map((l) => { const c = l.split(/[,\t;]/); return `${c[iRa]} ${c[iDec]}${iName >= 0 ? ` ${c[iName]}` : ""}`; }).join("\n")
      : lines.join("\n");
    $("#q-example-note").hidden = true;
    ev.target.value = "";
    runQuery();
  });
  $("#q-results").addEventListener("click", (ev) => {
    if (ev.target.closest("#q-csv")) return queryCSV();
    if (ev.target.closest("a")) return;
    const tr = ev.target.closest("tr[data-i]");
    if (tr) openDetail(state.objects[+tr.dataset.i]);
  });
  ["#f-text", "#f-zmin", "#f-zmax"].forEach((s) => $(s).addEventListener("input", debounce(applyFilters, 150)));
  ["#f-field", "#f-paper", "#f-lrd", "#f-jwst", "#f-spec", "#f-bl", "#f-multi", "#f-xray", "#f-var", "#f-miri"].forEach((s) => $(s).addEventListener("change", applyFilters));
  $("#f-reset").addEventListener("click", () => {
    ["#f-text", "#f-zmin", "#f-zmax"].forEach((s) => ($(s).value = ""));
    $("#f-field").value = ""; $("#f-paper").value = "";
    ["#f-spec", "#f-bl", "#f-multi", "#f-xray", "#f-var", "#f-miri"].forEach((s) => ($(s).checked = false));
    $("#f-lrd").checked = true;
    $("#f-jwst").checked = true;
    applyFilters();
  });
  $("#cat-download").addEventListener("click", catalogueCSV);
  $$("#cat-table th[data-sort]").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.sort;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : 1 };
    sortFiltered(); renderTable();
  }));
  $("#cat-pager").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-page]");
    if (!b) return;
    state.page += b.dataset.page === "next" ? 1 : -1;
    renderTable();
    $("#cat-table").scrollIntoView({ block: "start", behavior: "smooth" });
  });
  const rowOpen = (ev) => {
    if (ev.target.closest("a")) return;
    const tr = ev.target.closest("tr[data-i]");
    if (tr && (ev.type === "click" || ev.key === "Enter")) openDetail(state.objects[+tr.dataset.i]);
  };
  ["click", "keydown"].forEach((t) => { $("#cat-table tbody").addEventListener(t, rowOpen); $("#q-results").addEventListener(t, (ev) => ev.type === "keydown" && rowOpen(ev)); });
  $("#papers-table").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-show-paper]");
    if (!b) return;
    $("#f-paper").value = b.dataset.showPaper;
    $("#f-lrd").checked = false;
    $("#f-jwst").checked = false;
    applyFilters();
    selectTab("catalogue");
    $("#filters").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("#inbox-filter").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-inbox]");
    if (b) { state.inboxFilter = b.dataset.inbox; renderInbox(); }
  });
  $$(".tabs [role=tab]").forEach((t) => t.addEventListener("click", () => selectTab(t.id.replace("tab-", ""))));
  $(".tabs").addEventListener("keydown", (ev) => {
    if (!["ArrowLeft", "ArrowRight"].includes(ev.key)) return;
    const tabs = $$(".tabs [role=tab]"), i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    const next = tabs[(i + (ev.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    next.focus(); next.click();
  });
  $("#d-close").addEventListener("click", closeDetail);
  window.addEventListener("hashchange", () => {
    const h = decodeURIComponent(location.hash.slice(1));
    if (["catalogue", "charts", "papers", "inbox", "about"].includes(h)) selectTab(h, false);
  });
  window.addEventListener("resize", debounce(() => {
    state.chartsDirty = true;
    if (!$("#view-charts").hidden) renderCharts();
  }, 250));
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("#drawer").hidden) closeDetail(); });
  $("#drawer").addEventListener("click", (ev) => {
    const c = ev.target.closest("[data-copy]");
    if (c) return copyText(c.dataset.copy, c);
    const bib = ev.target.closest("[data-copy-bib]");
    if (bib) return copyText(bibFor(state.objects[+bib.dataset.copyBib]), bib);
  });
}
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

function renderStatic() {
  const m = state.meta;
  $("#stats").innerHTML = `<b>${fmtInt(m.n_lrd_jwst)}</b> JWST LRDs · <b>${fmtInt(m.n_lrd - m.n_lrd_jwst)}</b> wide-field candidates · <b>${m.n_papers}</b> papers<br><span class="muted small">Catalogue built ${esc(m.built.replace("T", " "))} UTC</span>`;
  $("#about-radius").textContent = m.match_radius_arcsec;
  $("#z-legend").innerHTML = `<span><i class="swatch sw-spec"></i>Spectroscopic z</span><span><i class="swatch sw-grism"></i>Grism z</span><span><i class="swatch sw-phot"></i>Photometric z</span><span><i class="swatch sw-none"></i>No z</span>`;
  $("#maintainer").textContent = `Maintained by ${CONFIG.maintainer}.`;
  $("#footer-text").textContent = `LRD Zoo. Object data belong to the authors of the papers listed. Built ${m.built} from ${m.n_papers} papers.`;
  if (CONFIG.repoUrl) {
    const r = CONFIG.repoUrl.replace(/\/$/, "");
    const link = $("#repo-link"); link.href = r; link.hidden = false;
    $("#contribute-text").innerHTML = `Each paper is a folder with a <code>meta.yaml</code> and an <code>objects.csv</code>; the format is in <a href="${esc(r)}/blob/main/data/SCHEMA.md">data/SCHEMA.md</a>. <a href="${esc(r)}/issues/new">Open an issue</a> to suggest a paper or report a wrong entry, or send a pull request.`;
  }
}

async function main() {
  initTheme();
  bindEvents();
  let data;
  try {
    const r = await fetch(CONFIG.dataUrl, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    data = await r.json();
  } catch (err) {
    $("#stats").textContent = `Could not load ${CONFIG.dataUrl} (${err.message}). Run scripts/build_catalog.py and serve this folder over HTTP.`;
    return;
  }
  prepare(data);
  renderStatic();
  fillSelects();
  renderPapers();
  applyFilters();
  $("#q-text").value = exampleInput();
  $("#q-example-note").hidden = false;
  runQuery();
  try {
    const r = await fetch(CONFIG.inboxUrl, { cache: "no-cache" });
    if (r.ok) state.inbox = await r.json();
  } catch { /* inbox is optional */ }
  renderInbox();

  const h = decodeURIComponent(location.hash.slice(1));
  const tabNames = ["catalogue", "charts", "papers", "inbox", "about"];
  if (tabNames.includes(h)) selectTab(h, false);
  else if (h) {
    const o = state.objects.find((x) => x._short === h || x.name === h);
    if (o) openDetail(o, false);
  }
}
main();
