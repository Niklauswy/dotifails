/* yurai/share — cliente */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const app = $("#app");
const touch = matchMedia("(hover: none)").matches;
const SPRITE_FRAMES = 10;

const store = {
  get(k, d) { try { const v = localStorage.getItem("ls:" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("ls:" + k, JSON.stringify(v)); } catch {} },
};

const state = {
  sort: store.get("sort", "date"),
  view: store.get("view", "grid"),
  q: "",
  channel: null,
  dir: null,
  listing: null,
};

/* ------------------------------------------------------------- helpers */
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = p => p.split("/").map(encodeURIComponent).join("/");
const join = (a, b) => (a ? a + "/" + b : b);
const parentOf = p => p.split("/").slice(0, -1).join("/");
const baseOf = p => p.split("/").pop();
const raw = (p, dl) => "/raw/" + enc(p) + (dl ? "?dl=1" : "");
const img = (kind, p) => `/api/${kind}?path=${encodeURIComponent(p)}`;
const extOf = n => (n.includes(".") ? n.split(".").pop().toLowerCase() : "");
const stripExt = n => n.replace(/\.[^.]+$/, "");

function fmtSize(n) {
  if (n == null) return "";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + " " + u[i];
}
function fmtDur(s) {
  if (!s && s !== 0) return "";
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0");
}
function fmtTotalDur(s) {
  const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min`;
}
const dateFmt = new Intl.DateTimeFormat("es-MX", { day: "numeric", month: "short", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false });
function fmtDate(d) { return dateFmt.format(d).replace(".", ""); }

function resLabel(e) {
  if (!e.height) return "";
  const h = Math.min(e.width, e.height) || e.height;
  if (h >= 2100) return "4K";
  if (h >= 1400) return "1440p";
  return h + "p";
}

const DATE_RE = /(\d{4})-(\d{2})-(\d{2})(?:[_ T](\d{2})[-:.](\d{2}))?/;
/** Interpreta nombres tipo canal__2025-11-11_02-17.mp4 */
function describe(e) {
  const base = stripExt(e.name);
  let channel = null, title = base, date = null;
  const m = base.match(DATE_RE);
  if (m) date = new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0));
  if (base.includes("__")) {
    channel = base.split("__")[0];
    title = channel;
  }
  const when = date || new Date(e.mtime * 1000);
  return { channel, title, date, when, hasTime: !!(m && m[4]) };
}

function hue(str) {
  let h = 0;
  for (const c of str) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 360;
}

const ICONS = {
  search: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  grid: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
  list: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  down: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v12m0 0-5-5m5 5 5-5M5 20h14"/></svg>',
  up: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20V8m0 0-5 5m5-5 5 5M5 4h14"/></svg>',
  folder: '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4h3.6c.6 0 1.2.3 1.6.7l1.2 1.3h6.6A2.5 2.5 0 0 1 21 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/></svg>',
  plus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  link: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
  zip: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="3" width="16" height="18" rx="2.5"/><path d="M12 3v2m0 2v2m0 2v2"/><rect x="10" y="13" width="4" height="4" rx="1"/></svg>',
  prev: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m15 6-6 6 6 6"/></svg>',
  next: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m9 6 6 6-6 6"/></svg>',
  play: '<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13a1 1 0 0 0 1.5.9l10-6.5a1 1 0 0 0 0-1.7l-10-6.5A1 1 0 0 0 8 5.5"/></svg>',
  file: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>',
  music: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/></svg>',
};

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("on");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("on"), 2200);
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.append(ta); ta.select();
    document.execCommand("copy"); ta.remove();
  }
  toast("Enlace copiado");
}

/* ----------------------------------------------------------------- api */
const cache = new Map();
async function ls(dir, fresh) {
  if (!fresh && cache.has(dir)) return cache.get(dir);
  const r = await fetch("/api/ls?path=" + encodeURIComponent(dir));
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Error");
  cache.set(dir, j);
  return j;
}

/* -------------------------------------------------------------- router */
function go(url) {
  history.pushState(null, "", url);
  route();
  window.scrollTo({ top: 0 });
}
document.addEventListener("click", e => {
  const a = e.target.closest("a[data-nav]");
  if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
  e.preventDefault();
  go(a.getAttribute("href"));
});
addEventListener("popstate", route);

function route() {
  stopPreviews();
  const path = decodeURIComponent(location.pathname);
  if (path.startsWith("/watch/")) return watch(path.slice(7));
  const dir = path.startsWith("/browse/") ? path.slice(8).replace(/\/+$/, "") : "";
  if (dir !== state.dir) { state.q = ""; state.channel = null; }
  browse(dir);
}

function crumbs(path, isFile) {
  const parts = path ? path.split("/") : [];
  let acc = "";
  const html = ['<a href="/" data-nav>inicio</a>'];
  parts.forEach((p, i) => {
    acc = join(acc, p);
    const last = i === parts.length - 1;
    const href = last && isFile ? "/watch/" + enc(acc) : "/browse/" + enc(acc);
    html.push('<span class="sep">/</span>', `<a href="${href}" data-nav>${esc(p)}</a>`);
  });
  $("#crumbs").innerHTML = html.join("");
  const last = $("#crumbs").lastElementChild;
  last && last.scrollIntoView({ inline: "end", block: "nearest" });
}

/* -------------------------------------------------------------- browse */
async function browse(dir) {
  state.dir = dir;
  crumbs(dir);
  document.title = (dir ? baseOf(dir) : "inicio") + " · yurai/share";
  if (!cache.has(dir)) app.innerHTML = '<div class="empty"><b>Sintonizando…</b>cargando carpeta</div>';
  try {
    state.listing = await ls(dir, true);
  } catch (err) {
    app.innerHTML = `<div class="empty"><b>Sin señal</b>${esc(err.message)}</div>`;
    return;
  }
  renderBrowse();
}

function sorted(entries) {
  const arr = entries.slice();
  const by = {
    date: (a, b) => describe(b).when - describe(a).when,
    name: (a, b) => a.name.localeCompare(b.name, "es", { numeric: true, sensitivity: "base" }),
    size: (a, b) => (b.size || 0) - (a.size || 0),
    dur: (a, b) => (b.duration || 0) - (a.duration || 0),
  }[state.sort];
  return arr.sort(by);
}

function channelsOf(entries) {
  const m = new Map();
  for (const e of entries) {
    if (e.kind === "dir") continue;
    const c = describe(e).channel;
    if (c) m.set(c, (m.get(c) || 0) + 1);
  }
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

function renderBrowse() {
  const { path, entries, readonly } = state.listing;
  const files = entries.filter(e => e.kind !== "dir");
  const totalSize = files.reduce((s, e) => s + (e.size || 0), 0);
  const videos = files.filter(e => e.kind === "video");
  const totalDur = videos.reduce((s, e) => s + (e.duration || 0), 0);
  const channels = channelsOf(entries);
  const name = path ? baseOf(path) : "inicio";

  app.innerHTML = `
    <section class="hero">
      <h1>${esc(name)}<span class="dim">.</span></h1>
      <div class="stats">
        <div><b>${files.length}</b>archivos</div>
        ${videos.length ? `<div><b>${videos.length}</b>videos</div>` : ""}
        ${totalDur ? `<div><b>${fmtTotalDur(totalDur)}</b>de grabación</div>` : ""}
        <div><b>${fmtSize(totalSize) || "0 B"}</b>en total</div>
      </div>
    </section>
    <div class="toolbar">
      <label class="search">${ICONS.search}<input id="q" type="search" placeholder="Buscar en esta carpeta" value="${esc(state.q)}" autocomplete="off"><kbd>/</kbd></label>
      <div class="seg" id="sort">
        ${sortOpts(videos.length).map(([k, l]) => `<button data-sort="${k}" class="${state.sort === k ? "on" : ""}">${l}</button>`).join("")}
      </div>
      <label class="seg sort-select">
        <select id="sort-sel" aria-label="Ordenar">
          ${sortOpts(videos.length).map(([k, l]) => `<option value="${k}" ${state.sort === k ? "selected" : ""}>${l}</option>`).join("")}
        </select>
      </label>
      <div class="seg" id="view">
        <button data-view="grid" class="${state.view === "grid" ? "on" : ""}" aria-label="Cuadrícula">${ICONS.grid}</button>
        <button data-view="list" class="${state.view === "list" ? "on" : ""}" aria-label="Lista">${ICONS.list}</button>
      </div>
      ${readonly ? "" : `
        <button class="btn" id="mk" aria-label="Nueva carpeta">${ICONS.plus}<span class="lbl">Carpeta</span></button>
        <button class="btn primary" id="upl" aria-label="Subir">${ICONS.up}<span class="lbl">Subir</span></button>`}
      <a class="btn" href="/zip/${enc(path)}" aria-label="Descargar carpeta" title="Descargar carpeta como .zip">${ICONS.zip}<span class="lbl">.zip</span></a>
    </div>
    ${channels.length > 1 ? `
      <div class="chips" id="chips">
        <button class="chip ${state.channel ? "" : "on"}" data-ch="">Todos <small>${files.length}</small></button>
        ${channels.map(([c, n]) => `<button class="chip ${state.channel === c ? "on" : ""}" data-ch="${esc(c)}">${esc(c)} <small>${n}</small></button>`).join("")}
      </div>` : ""}
    <div id="results"></div>`;

  $("#q").addEventListener("input", e => { state.q = e.target.value; renderResults(); });
  $("#sort").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    state.sort = b.dataset.sort; store.set("sort", state.sort);
    $$("#sort button").forEach(x => x.classList.toggle("on", x === b));
    renderResults();
  });
  $("#sort-sel").addEventListener("change", e => {
    state.sort = e.target.value; store.set("sort", state.sort);
    $$("#sort button").forEach(x => x.classList.toggle("on", x.dataset.sort === state.sort));
    renderResults();
  });
  $("#view").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    state.view = b.dataset.view; store.set("view", state.view);
    $$("#view button").forEach(x => x.classList.toggle("on", x === b));
    renderResults();
  });
  $("#chips")?.addEventListener("click", e => {
    const b = e.target.closest(".chip"); if (!b) return;
    state.channel = b.dataset.ch || null;
    $$("#chips .chip").forEach(x => x.classList.toggle("on", x === b));
    renderResults();
  });
  $("#upl")?.addEventListener("click", () => $("#picker").click());
  $("#mk")?.addEventListener("click", mkdir);
  renderResults();
}

function sortOpts(hasVideos) {
  return [["date", "Fecha"], ["name", "Nombre"], ["size", "Tamaño"]].concat(hasVideos ? [["dur", "Duración"]] : []);
}

function filtered() {
  const q = state.q.trim().toLowerCase();
  return sorted(state.listing.entries).filter(e => {
    if (q && !e.name.toLowerCase().includes(q)) return false;
    if (state.channel && e.kind !== "dir" && describe(e).channel !== state.channel) return false;
    if (state.channel && e.kind === "dir") return false;
    return true;
  });
}

function renderResults() {
  stopPreviews();
  const items = filtered();
  const dir = state.listing.path;
  const dirs = items.filter(e => e.kind === "dir").sort((a, b) => a.name.localeCompare(b.name, "es", { numeric: true }));
  const files = items.filter(e => e.kind !== "dir");
  const box = $("#results");
  if (!items.length) {
    box.innerHTML = state.listing.entries.length
      ? '<div class="empty"><b>Nada por aquí</b>prueba con otra búsqueda</div>'
      : `<div class="empty"><b>Carpeta vacía</b>${state.listing.readonly ? "" : "arrastra archivos aquí o usa “Subir”"}</div>`;
    return;
  }
  let html = "";
  if (dirs.length) {
    html += `<div class="section-label">Carpetas · ${dirs.length}</div><div class="grid dirs">` +
      dirs.map((e, i) => `
        <a class="folder card" style="--i:${i}" href="/browse/${enc(join(dir, e.name))}" data-nav>
          <span class="ficon">${ICONS.folder}</span>
          <span class="txt"><div class="title">${esc(e.name)}</div><div class="meta">${e.count} elemento${e.count === 1 ? "" : "s"}</div></span>
        </a>`).join("") + "</div>";
  }
  if (files.length) {
    if (dirs.length) html += `<div class="section-label">Archivos · ${files.length}</div>`;
    html += state.view === "list"
      ? `<div class="list">${files.map((e, i) => rowHTML(e, dir, i)).join("")}</div>`
      : `<div class="grid">${files.map((e, i) => cardHTML(e, dir, i)).join("")}</div>`;
  }
  box.innerHTML = html;
  wireThumbs(box);
}

function hrefFor(e, dir) {
  const p = join(dir, e.name);
  if (e.kind === "video" || e.kind === "audio") return { href: "/watch/" + enc(p), nav: true };
  if (e.kind === "image") return { href: raw(p), lb: true };
  return { href: raw(p), blank: true };
}

function thumbHTML(e, dir) {
  const p = join(dir, e.name);
  const pos = e.kind === "video" ? store.get("pos:" + p, null) : null;
  const pct = pos && e.duration ? Math.min(100, (pos / e.duration) * 100) : 0;
  const res = resLabel(e);
  if (e.kind === "video" || e.kind === "image") {
    return `<div class="thumb" ${e.kind === "video" ? `data-sprite="${esc(p)}"` : ""}>
      <div class="ph">${e.kind === "video" ? ICONS.play : ""}</div>
      <img loading="lazy" decoding="async" alt="" src="${img("thumb", p)}">
      ${e.kind === "video" ? '<div class="sprite"></div><span class="scrub"></span>' : ""}
      <span class="loading-bar"></span>
      ${res ? `<span class="badge res">${res}</span>` : ""}
      ${e.duration ? `<span class="badge dur">${fmtDur(e.duration)}</span>` : ""}
      ${pct > 1 ? `<span class="progress" style="width:${pct}%"></span>` : ""}
    </div>`;
  }
  const ext = extOf(e.name);
  return `<div class="thumb loaded">
    <div class="ph">${e.kind === "audio" ? ICONS.music : ICONS.file}</div>
    ${ext ? `<span class="badge ext">.${esc(ext)}</span>` : ""}
    ${e.duration ? `<span class="badge dur">${fmtDur(e.duration)}</span>` : ""}
  </div>`;
}

function metaLine(e, d) {
  const parts = [];
  parts.push(fmtDate(d.when) + (d.hasTime ? " · " + timeFmt.format(d.when) : ""));
  if (e.size != null) parts.push(fmtSize(e.size));
  return parts.map(esc).join('<span class="dot">·</span>');
}

function linkAttrs(e, dir) {
  const h = hrefFor(e, dir);
  return `href="${h.href}" ${h.nav ? "data-nav" : ""} ${h.blank ? 'target="_blank" rel="noopener"' : ""} ${h.lb ? `data-lb-open="${esc(join(dir, e.name))}"` : ""}`;
}

function cardHTML(e, dir, i) {
  const d = describe(e);
  const p = join(dir, e.name);
  const av = d.channel ? `<span class="avatar" style="background:hsl(${hue(d.channel)} 85% 68%)">${esc(d.channel[0].toUpperCase())}</span>` : "";
  const title = d.channel ? d.title : stripExt(e.name);
  return `<article class="card" style="--i:${i}" title="${esc(e.name)}">
    <a class="cover" ${linkAttrs(e, dir)} aria-label="${esc(e.name)}"></a>
    <a class="dl" href="${raw(p, true)}" download aria-label="Descargar">${ICONS.down}</a>
    ${thumbHTML(e, dir)}
    <div class="info">${av}<div class="txt"><div class="title">${esc(title)}</div><div class="meta">${metaLine(e, d)}</div></div></div>
  </article>`;
}

function rowHTML(e, dir, i) {
  const d = describe(e);
  const p = join(dir, e.name);
  return `<div class="row" style="--i:${i}">
    <a class="cover" ${linkAttrs(e, dir)} aria-label="${esc(e.name)}"></a>
    ${thumbHTML(e, dir)}
    <div class="txt"><div class="title">${esc(e.name)}</div><div class="meta">${metaLine(e, d)}${e.duration ? `<span class="dot">·</span>${fmtDur(e.duration)}` : ""}</div></div>
    <div class="end"><span class="sz">${fmtSize(e.size)}</span><a class="dl" href="${raw(p, true)}" download aria-label="Descargar">${ICONS.down}</a></div>
  </div>`;
}

/* ----------------------------------------------------- thumbs/previews */
function wireThumbs(root) {
  $$(".thumb img", root).forEach(im => {
    const done = ok => {
      im.closest(".thumb").classList.add("loaded");
      if (ok) { im.classList.add("ok"); im.previousElementSibling?.remove(); } else im.remove();
    };
    if (im.complete && im.naturalWidth) done(true);
    else { im.onload = () => done(true); im.onerror = () => done(false); }
  });
  $$(".thumb[data-sprite]", root).forEach(th => {
    const card = th.closest(".card, .row, .mini");
    if (!touch) {
      card.addEventListener("pointerenter", () => loadSprite(th));
      card.addEventListener("pointermove", ev => scrubTo(th, ev));
      card.addEventListener("pointerleave", () => th.classList.remove("scrubbing"));
    } else {
      previewObserver.observe(th);
    }
  });
}

function loadSprite(th) {
  if (th._sprite) return th._sprite;
  th._sprite = new Promise(res => {
    const im = new Image();
    im.onload = () => {
      th.querySelector(".sprite").style.backgroundImage = `url("${im.src}")`;
      th._spriteOk = true; res(true);
    };
    im.onerror = () => res(false);
    im.src = img("sprite", th.dataset.sprite);
  });
  return th._sprite;
}

function setFrame(th, idx) {
  const sp = th.querySelector(".sprite");
  sp.style.backgroundPosition = `${(idx / (SPRITE_FRAMES - 1)) * 100}% 0`;
  th.querySelector(".scrub").style.width = ((idx + 1) / SPRITE_FRAMES) * 100 + "%";
}

function scrubTo(th, ev) {
  if (!th._spriteOk) return;
  const r = th.getBoundingClientRect();
  const x = Math.max(0, Math.min(.999, (ev.clientX - r.left) / r.width));
  setFrame(th, Math.floor(x * SPRITE_FRAMES));
  th.classList.add("scrubbing");
}

/* En iPhone: las tarjetas totalmente visibles reproducen su storyboard */
const playing = new Set();
const previewObserver = "IntersectionObserver" in window ? new IntersectionObserver(entries => {
  for (const en of entries) {
    const th = en.target;
    if (en.isIntersecting && en.intersectionRatio > .85) {
      clearTimeout(th._wait);
      th._wait = setTimeout(async () => {
        if (!(await loadSprite(th))) return;
        if (th._timer) return;
        let i = 0;
        setFrame(th, 0);
        th.classList.add("scrubbing");
        th._timer = setInterval(() => { i = (i + 1) % SPRITE_FRAMES; setFrame(th, i); }, 650);
        playing.add(th);
      }, 700);
    } else {
      clearTimeout(th._wait);
      stopOne(th);
    }
  }
}, { threshold: [0, .85, 1] }) : { observe() {}, disconnect() {} };

function stopOne(th) {
  clearInterval(th._timer); th._timer = null;
  th.classList.remove("scrubbing");
  playing.delete(th);
}
function stopPreviews() {
  playing.forEach(stopOne);
  previewObserver.disconnect();
}

/* --------------------------------------------------------------- watch */
async function watch(p) {
  const dir = parentOf(p);
  crumbs(p, true);
  let listing;
  try { listing = await ls(dir); } catch (err) {
    app.innerHTML = `<div class="empty"><b>Sin señal</b>${esc(err.message)}</div>`; return;
  }
  const e = listing.entries.find(x => x.name === baseOf(p));
  if (!e) { app.innerHTML = '<div class="empty"><b>No encontrado</b>el archivo ya no existe</div>'; return; }
  const d = describe(e);
  document.title = (d.channel ? d.title + " · " + fmtDate(d.when) : stripExt(e.name)) + " · yurai/share";

  const playlist = sorted(listing.entries.filter(x => x.kind === e.kind));
  const idx = playlist.findIndex(x => x.name === e.name);
  const prev = playlist[idx - 1], next = playlist[idx + 1];
  const isVideo = e.kind === "video";
  const specs = [
    e.duration && ["duración", fmtDur(e.duration)],
    e.width && ["resolución", `${e.width}×${e.height}`],
    e.vcodec && ["video", e.vcodec],
    e.acodec && ["audio", e.acodec],
    ["tamaño", fmtSize(e.size)],
    ["fecha", fmtDate(d.when) + (d.hasTime ? " " + timeFmt.format(d.when) : "")],
  ].filter(Boolean);

  app.innerHTML = `
    <div class="watch">
      <div>
        <div class="stage">
          ${isVideo
            ? `<video id="player" controls playsinline preload="metadata" poster="${img("thumb", p)}" src="${raw(p)}"></video>`
            : `<audio id="player" controls preload="metadata" src="${raw(p)}"></audio>`}
        </div>
        <div class="w-head">
          <div class="kicker">${d.channel ? esc(d.channel) : esc(extOf(e.name))}<span style="color:var(--mute)">${idx + 1} / ${playlist.length}</span></div>
          <h1>${esc(d.channel ? fmtDate(d.when) + (d.hasTime ? " · " + timeFmt.format(d.when) : "") : stripExt(e.name))}</h1>
        </div>
        <div class="specs">${specs.map(([k, v]) => `<span class="spec">${k} <b>${esc(v)}</b></span>`).join("")}</div>
        <div class="actions">
          <a class="btn primary" href="${raw(p, true)}" download>${ICONS.down}<span class="lbl">Descargar</span></a>
          <button class="btn" id="cp">${ICONS.link}<span class="lbl">Copiar enlace</span></button>
          ${prev ? `<a class="btn" href="/watch/${enc(join(dir, prev.name))}" data-nav>${ICONS.prev}<span class="lbl">Anterior</span></a>` : ""}
          ${next ? `<a class="btn" href="/watch/${enc(join(dir, next.name))}" data-nav><span class="lbl">Siguiente</span>${ICONS.next}</a>` : ""}
        </div>
      </div>
      <aside class="side">
        <div class="section-label">En esta carpeta · ${playlist.length}</div>
        <div class="side-list">
          ${playlist.map(x => {
            const dx = describe(x);
            const xp = join(dir, x.name);
            return `<div class="mini ${x.name === e.name ? "now" : ""}">
              <a class="cover" href="/watch/${enc(xp)}" data-nav aria-label="${esc(x.name)}" style="position:absolute;inset:0;z-index:2"></a>
              ${thumbHTML(x, dir)}
              <div class="txt"><div class="title">${esc(dx.channel || stripExt(x.name))}</div><div class="meta">${metaLine(x, dx)}</div></div>
            </div>`;
          }).join("")}
        </div>
      </aside>
    </div>`;

  wireThumbs(app);
  const now = $(".mini.now");
  if (now && innerWidth > 1080) now.scrollIntoView({ block: "center" });
  $("#cp").onclick = () => copy(location.href);
  setupPlayer($("#player"), p, next && "/watch/" + enc(join(dir, next.name)));
}

function setupPlayer(v, p, nextUrl) {
  const key = "pos:" + p;
  const saved = store.get(key, null);
  let lastSave = 0;
  v.addEventListener("loadedmetadata", () => {
    if (saved && saved > 15 && saved < v.duration - 20) {
      const box = document.createElement("div");
      box.className = "resume";
      box.innerHTML = `<span>Ibas en ${fmtDur(saved)}</span><button class="go">Continuar</button><button>Desde inicio</button>`;
      v.parentNode.append(box);
      box.querySelector(".go").onclick = () => { v.currentTime = saved; v.play(); box.remove(); };
      box.lastElementChild.onclick = () => { store.set(key, null); v.currentTime = 0; v.play(); box.remove(); };
      setTimeout(() => box.remove(), 12000);
    }
  }, { once: true });
  v.addEventListener("timeupdate", () => {
    const t = v.currentTime;
    if (Math.abs(t - lastSave) < 5) return;
    lastSave = t;
    store.set(key, t > v.duration - 20 ? null : Math.floor(t));
  });
  v.addEventListener("ended", () => { store.set(key, null); if (nextUrl) toast("Siguiente en la lista →"); });
  v.play().catch(() => {});
}

/* -------------------------------------------------------------- lightbox */
const lb = { list: [], i: 0 };
document.addEventListener("click", e => {
  const a = e.target.closest("[data-lb-open]");
  if (!a || e.metaKey || e.ctrlKey) return;
  e.preventDefault();
  const dir = state.listing.path;
  lb.list = filtered().filter(x => x.kind === "image").map(x => join(dir, x.name));
  lb.i = Math.max(0, lb.list.indexOf(a.dataset.lbOpen));
  showLb();
});
function showLb() {
  const p = lb.list[lb.i];
  $("#lb-img").src = raw(p);
  $("#lb-cap").textContent = `${baseOf(p)} — ${lb.i + 1} / ${lb.list.length}`;
  $("#lightbox").hidden = false;
  document.body.style.overflow = "hidden";
}
function lbMove(d) { if (!lb.list.length) return; lb.i = (lb.i + d + lb.list.length) % lb.list.length; showLb(); }
function lbClose() { $("#lightbox").hidden = true; $("#lb-img").src = ""; document.body.style.overflow = ""; }
$("#lightbox").addEventListener("click", e => {
  const act = e.target.dataset.lb;
  if (act === "close" || e.target.id === "lightbox" || e.target.tagName === "FIGURE") lbClose();
  else if (act === "prev") lbMove(-1);
  else if (act === "next") lbMove(1);
});
let tx = null;
$("#lightbox").addEventListener("touchstart", e => { tx = e.touches[0].clientX; }, { passive: true });
$("#lightbox").addEventListener("touchend", e => {
  if (tx === null) return;
  const dx = e.changedTouches[0].clientX - tx;
  if (Math.abs(dx) > 50) lbMove(dx < 0 ? 1 : -1);
  tx = null;
});

/* ------------------------------------------------------------ keyboard */
document.addEventListener("keydown", e => {
  if (!$("#lightbox").hidden) {
    if (e.key === "Escape") lbClose();
    if (e.key === "ArrowRight") lbMove(1);
    if (e.key === "ArrowLeft") lbMove(-1);
    return;
  }
  if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
    const q = $("#q"); if (q) { e.preventDefault(); q.focus(); }
  }
  if (e.key === "Escape" && document.activeElement?.id === "q") document.activeElement.blur();
});

/* -------------------------------------------------------------- upload */
const currentDir = () => (location.pathname.startsWith("/watch/") ? parentOf(decodeURIComponent(location.pathname.slice(7))) : state.dir || "");

function uploadFiles(files) {
  if (state.listing?.readonly) return toast("Servidor en modo solo lectura");
  const dir = currentDir();
  const box = $("#uploads");
  let pending = files.length;
  for (const f of files) {
    const el = document.createElement("div");
    el.className = "up";
    el.innerHTML = `<div class="n"><span>${esc(f.name)}</span><span>0%</span></div><div class="bar"><i></i></div>`;
    box.append(el);
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/upload?dir=${encodeURIComponent(dir)}&name=${encodeURIComponent(f.name)}`);
    xhr.upload.onprogress = ev => {
      if (!ev.lengthComputable) return;
      const pct = Math.round((ev.loaded / ev.total) * 100);
      el.querySelector("i").style.width = pct + "%";
      el.querySelector(".n span:last-child").textContent = `${pct}% · ${fmtSize(ev.loaded)}`;
    };
    xhr.onload = () => {
      const ok = xhr.status === 200;
      el.classList.add(ok ? "done" : "err");
      el.querySelector("i").style.width = "100%";
      el.querySelector(".n span:last-child").textContent = ok ? "listo" : (JSON.parse(xhr.responseText || "{}").error || "error");
      setTimeout(() => el.remove(), ok ? 2500 : 6000);
      if (--pending === 0 && !location.pathname.startsWith("/watch/")) { cache.delete(dir); browse(dir); }
    };
    xhr.onerror = () => { el.classList.add("err"); el.querySelector(".n span:last-child").textContent = "falló"; pending--; };
    xhr.send(f);
  }
}
$("#picker").addEventListener("change", e => { uploadFiles([...e.target.files]); e.target.value = ""; });

let dragDepth = 0;
const hasFiles = e => [...(e.dataTransfer?.types || [])].includes("Files");
addEventListener("dragenter", e => {
  if (!hasFiles(e) || state.listing?.readonly) return;
  dragDepth++;
  $("#drop-target").textContent = "→ /" + currentDir();
  $("#drop").classList.add("on");
});
addEventListener("dragover", e => { if (hasFiles(e)) e.preventDefault(); });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#drop").classList.remove("on"); } });
addEventListener("drop", e => {
  if (!hasFiles(e)) return;
  e.preventDefault(); dragDepth = 0; $("#drop").classList.remove("on");
  if (!state.listing?.readonly) uploadFiles([...e.dataTransfer.files]);
});

async function mkdir() {
  const name = prompt("Nombre de la nueva carpeta");
  if (!name) return;
  const dir = state.dir || "";
  const r = await fetch(`/api/mkdir?dir=${encodeURIComponent(dir)}&name=${encodeURIComponent(name)}`, { method: "POST" });
  const j = await r.json();
  if (!r.ok) return toast(j.error || "No se pudo crear");
  toast("Carpeta creada");
  cache.delete(dir);
  browse(dir);
}

route();
