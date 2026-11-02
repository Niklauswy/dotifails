"use strict";
/* Wysun LANShare page: browse what is shared, preview, view full screen, download and (when the
   owner allowed it) upload. Talks to server.py's JSON API; no colours here (theme.css). */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const wide = matchMedia("(min-width: 1100px)");
const hover = matchMedia("(hover: hover)");
const SPRITE_FRAMES = 10;

const store = {
  get: (k, d) => { try { const v = localStorage.getItem("lanshare:" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem("lanshare:" + k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const state = {
  info: null,
  dir: "",
  listing: null,
  items: [],                       // what the list shows, in order
  selected: null,                  // name of the selected item
  sort: store.get("sort", "date"),
  view: store.get("view", "list"),
  query: "",
};

/* ---------------------------------------------------------------- helpers */
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = p => p.split("/").map(encodeURIComponent).join("/");
const join = (a, b) => (a ? a + "/" + b : b);
const raw = (p, dl) => "/raw/" + enc(p) + (dl ? "?dl=1" : "");
const pic = (kind, p) => `/api/${kind}?path=${encodeURIComponent(p)}`;
const fold = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const pathOf = e => join(state.dir, e.name);

function fmtSize(n) {
  if (n == null) return "";
  if (n < 1024) return n + " B";
  const u = ["KB", "MB", "GB", "TB"];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return (n >= 100 ? Math.round(n) : n.toFixed(1).replace(".0", "")).toString().replace(".", ",") + " " + u[i];
}
function fmtDur(s) {
  if (!s) return "";
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
const dayFmt = new Intl.DateTimeFormat("es", { day: "numeric", month: "short" });
const yearFmt = new Intl.DateTimeFormat("es", { day: "numeric", month: "short", year: "numeric" });
const fullFmt = new Intl.DateTimeFormat("es", { dateStyle: "long", timeStyle: "short" });
function fmtDate(t) {
  const d = new Date(t * 1000), now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (d.getTime() >= start) return "hoy";
  if (d.getTime() >= start - 86400000) return "ayer";
  return (d.getFullYear() === now.getFullYear() ? dayFmt : yearFmt).format(d).replace(".", "");
}
function quality(e) {
  const h = Math.min(e.width || 0, e.height || 0) || e.height;
  if (!h) return "";
  if (h >= 2000) return "4K";
  return h + "p";
}
const count = n => (n === 1 ? "1 elemento" : `${n} elementos`);

const ICON = { dir: "folder", video: "movie", image: "image", audio: "music_note", pdf: "picture_as_pdf",
               text: "description", archive: "folder_zip", file: "draft" };

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("on");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("on"), 2600);
}

async function api(url, opts) {
  const r = await fetch(url, opts);
  if (r.status === 401) { showGate(); throw new Error("locked"); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Error " + r.status);
  return j;
}

/* ---------------------------------------------------------------- start */
async function start() {
  document.fonts?.load('24px "Material Symbols Rounded"', "folder").finally(() => document.documentElement.classList.add("icons"));
  setTimeout(() => document.documentElement.classList.add("icons"), 4000);
  try {
    state.info = await (await fetch("/api/info")).json();
  } catch {
    document.body.textContent = "No se pudo conectar.";
    return;
  }
  document.title = `${state.info.title} · Wysun`;
  if (state.info.locked) return showGate();
  enter();
}

function showGate() {
  $("#shell").hidden = true;
  $("#gate").hidden = false;
  $("#gate-host").textContent = "Wysun";
  setTimeout(() => $("#gate-input").focus(), 50);
}

$("#gate-form").addEventListener("submit", async ev => {
  ev.preventDefault();
  const card = $("#gate-form");
  const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json", "X-Wysun": "1" },
                                         body: JSON.stringify({ clave: $("#gate-input").value }) });
  if (r.ok) { $("#gate").hidden = true; state.info.locked = false; return enter(); }
  const j = await r.json().catch(() => ({}));
  $("#gate-error").textContent = j.error || "No se pudo entrar";
  card.classList.remove("shake"); void card.offsetWidth; card.classList.add("shake");
  $("#gate-input").select();
});

function enter() {
  $("#shell").hidden = false;
  $("#lock").hidden = !state.info.password;
  $("#upload").hidden = $("#upload-fab").hidden = $("#mkdir").hidden = !state.info.uploads;
  setView(state.view);
  route();
}

/* ---------------------------------------------------------------- routing */
const dirFromUrl = () => decodeURIComponent(location.pathname.startsWith("/b/") ? location.pathname.slice(3) : "").replace(/\/+$/, "");
function go(dir) {
  history.pushState(null, "", dir ? "/b/" + enc(dir) : "/");
  route();
}
addEventListener("popstate", () => { if (!$("#viewer").hidden) closeViewer(true); else route(); });

async function route() {
  const dir = dirFromUrl();
  let listing;
  try {
    listing = await api("/api/ls?path=" + encodeURIComponent(dir));
  } catch (err) {
    if (err.message === "locked") return;
    if (dir) return go(dir.split("/").slice(0, -1).join("/"));
    $("#items").innerHTML = `<div class="empty"><span class="ms">cloud_off</span><b>No disponible</b>${esc(err.message)}</div>`;
    return;
  }
  const changed = dir !== state.dir;
  state.dir = dir;
  state.listing = listing;
  if (changed) { state.selected = null; state.query = ""; $("#q").value = ""; }
  crumbs();
  const where = dir ? dir.split("/").pop() : listing.title;
  $("#q").placeholder = `Buscar en ${where}`;
  const all = !dir && listing.mode === "list";
  $("#zip").href = "/zip/" + enc(dir);
  $("#zip-label").textContent = all ? "Descargar todo" : "Descargar carpeta";
  $("#zip").title = all ? "Descargar todo (.zip)" : "Descargar carpeta (.zip)";
  render();
}

function crumbs() {
  const nav = $("#crumbs");
  const parts = state.dir ? state.dir.split("/") : [];
  const rootName = state.listing.title;
  let html = parts.length ? `<a href="/" data-dir=""><span class="ms">home</span>${esc(rootName)}</a>`
                          : `<b><span class="ms">home</span>${esc(rootName)}</b>`;
  parts.forEach((p, i) => {
    const path = parts.slice(0, i + 1).join("/");
    html += `<span class="ms sep">chevron_right</span>`;
    html += i === parts.length - 1 ? `<b>${esc(p)}</b>` : `<a href="/b/${enc(path)}" data-dir="${esc(path)}">${esc(p)}</a>`;
  });
  nav.innerHTML = html;
  nav.scrollLeft = nav.scrollWidth;
}
$("#crumbs").addEventListener("click", ev => {
  const a = ev.target.closest("a[data-dir]");
  if (!a) return;
  ev.preventDefault();
  go(a.dataset.dir);
});

/* ---------------------------------------------------------------- list */
function ordered(entries) {
  const by = {
    date: (a, b) => (b.mtime || 0) - (a.mtime || 0),
    name: (a, b) => a.name.localeCompare(b.name, "es", { numeric: true, sensitivity: "base" }),
    size: (a, b) => (b.size ?? -1) - (a.size ?? -1),
  }[state.sort];
  const nameOrder = (a, b) => a.name.localeCompare(b.name, "es", { numeric: true, sensitivity: "base" });
  return [...entries].sort((a, b) => ((b.kind === "dir") - (a.kind === "dir")) || by(a, b) || nameOrder(a, b));
}

function render() {
  const q = fold(state.query.trim());
  state.items = ordered(state.listing.entries.filter(e => !q || fold(e.name).includes(q)));
  const box = $("#items");
  if (!state.items.length) {
    box.innerHTML = q
      ? `<div class="empty"><span class="ms">search_off</span><b>Sin resultados</b>Nada coincide con «${esc(state.query)}»</div>`
      : `<div class="empty"><span class="ms">folder_open</span><b>Carpeta vacía</b>${state.info.uploads ? "Arrastra archivos aquí o usa «Subir»" : ""}</div>`;
  } else {
    box.innerHTML = state.items.map(rowHTML).join("");
    wireThumbs(box);
  }
  if (!state.items.some(e => e.name === state.selected)) state.selected = null;
  markSelected();
  renderPane();
}

function thumbHTML(e) {
  const p = pathOf(e);
  const icon = `<span class="ms${e.kind === "dir" ? " fill" : ""}">${ICON[e.kind] || "draft"}</span>`;
  if (e.kind === "image") return `<span class="thumb k-image">${icon}<img loading="lazy" alt="" src="${pic("thumb", p)}"></span>`;
  if (e.kind === "video") {
    return `<span class="thumb k-video" data-sprite="${esc(p)}">${icon}<img loading="lazy" alt="" src="${pic("thumb", p)}">` +
           `<span class="sprite"></span><span class="scrub"></span>${e.duration ? `<span class="dur">${fmtDur(e.duration)}</span>` : ""}</span>`;
  }
  return `<span class="thumb k-${e.kind}">${icon}</span>`;
}

function metaOf(e) {
  if (e.kind === "dir") return [count(e.count || 0), fmtDate(e.mtime)];
  return [fmtSize(e.size), quality(e), fmtDate(e.mtime)].filter(Boolean);
}

function rowHTML(e, i) {
  const dir = e.kind === "dir";
  const action = dir
    ? `<span class="icon-btn act" aria-hidden="true"><span class="ms">chevron_right</span></span>`
    : `<a class="icon-btn act" href="${raw(pathOf(e), true)}" download title="Descargar ${esc(e.name)}" data-stop><span class="ms">download</span></a>`;
  return `<div class="row layer" role="listitem" tabindex="-1" data-name="${esc(e.name)}" style="--i:${Math.min(i, 24)}">
    <span class="name">${thumbHTML(e)}<span class="text"><span class="title" title="${esc(e.name)}">${esc(e.name)}</span><span class="meta">${metaOf(e).join(" · ")}</span></span></span>
    <span class="col">${dir ? count(e.count || 0) : fmtSize(e.size)}</span>
    <span class="col">${fmtDur(e.duration) || "—"}</span>
    <span class="col">${fmtDate(e.mtime)}</span>
    ${action}
  </div>`;
}

function entry(name) { return state.items.find(e => e.name === name); }
function rowOf(name) { return $$("#items .row").find(r => r.dataset.name === name); }

function markSelected() {
  $$("#items .row").forEach(r => r.setAttribute("aria-selected", String(r.dataset.name === state.selected)));
}

function select(name, focus) {
  state.selected = name;
  markSelected();
  renderPane();
  const r = rowOf(name);
  if (r && focus) { r.focus({ preventScroll: true }); r.scrollIntoView({ block: "nearest" }); }
}

function open(e) {
  if (!e) return;
  if (e.kind === "dir") return go(pathOf(e));
  openViewer(e);
}

$("#items").addEventListener("click", ev => {
  if (ev.target.closest("[data-stop]")) return;
  const r = ev.target.closest(".row");
  if (!r) return;
  const e = entry(r.dataset.name);
  // Wide screens select first (preview pane); phones and folders open at once.
  if (e.kind === "dir" || !wide.matches) return open(e);
  select(e.name, true);
});
$("#items").addEventListener("dblclick", ev => {
  const r = ev.target.closest(".row");
  if (r && !ev.target.closest("[data-stop]")) open(entry(r.dataset.name));
});

/* sprites: hover scrubs on a mouse; on touch the fully visible ones play by themselves */
function wireThumbs(root) {
  $$(".thumb img", root).forEach(im => {
    const done = ok => { if (ok) { im.classList.add("ok"); } else im.remove(); };
    if (im.complete && im.naturalWidth) done(true);
    else { im.onload = () => done(true); im.onerror = () => done(false); }
  });
  $$(".thumb[data-sprite]", root).forEach(th => {
    if (hover.matches) {
      th.addEventListener("pointerenter", () => loadSprite(th));
      th.addEventListener("pointermove", ev => scrubTo(th, ev));
      th.addEventListener("pointerleave", () => th.classList.remove("scrubbing"));
    } else {
      previewObserver.observe(th);
    }
  });
}
function loadSprite(th) {
  if (th._sprite) return th._sprite;
  th._sprite = new Promise(res => {
    const im = new Image();
    im.onload = () => { th.querySelector(".sprite").style.backgroundImage = `url("${im.src}")`; th._ok = true; res(true); };
    im.onerror = () => res(false);
    im.src = pic("sprite", th.dataset.sprite);
  });
  return th._sprite;
}
function setFrame(th, i) {
  th.querySelector(".sprite").style.backgroundPosition = `${(i / (SPRITE_FRAMES - 1)) * 100}% 0`;
  th.querySelector(".scrub").style.width = ((i + 1) / SPRITE_FRAMES) * 100 + "%";
}
function scrubTo(th, ev) {
  if (!th._ok) return;
  const r = th.getBoundingClientRect();
  setFrame(th, Math.floor(Math.max(0, Math.min(0.999, (ev.clientX - r.left) / r.width)) * SPRITE_FRAMES));
  th.classList.add("scrubbing");
}
const previewObserver = "IntersectionObserver" in window ? new IntersectionObserver(list => {
  for (const en of list) {
    const th = en.target;
    clearTimeout(th._wait);
    if (en.isIntersecting && en.intersectionRatio > 0.85) {
      th._wait = setTimeout(async () => {
        if (!(await loadSprite(th)) || th._timer) return;
        let i = 0;
        setFrame(th, 0);
        th.classList.add("scrubbing");
        th._timer = setInterval(() => setFrame(th, (i = (i + 1) % SPRITE_FRAMES)), 650);
      }, 700);
    } else {
      clearInterval(th._timer); th._timer = null; th.classList.remove("scrubbing");
    }
  }
}, { threshold: [0, 0.85, 1] }) : { observe() {} };

/* ---------------------------------------------------------------- preview pane */
async function textOf(p) {
  const r = await fetch(raw(p), { headers: { Range: "bytes=0-65535" } });
  return r.ok ? r.text() : "";
}

function stageHTML(e, where) {
  const p = pathOf(e);
  switch (e.kind) {
    case "video":
      // In the pane a still with a play button (hover runs through the video's frames); the viewer plays it.
      if (where === "pane") {
        return `<button class="poster thumb" data-sprite="${esc(p)}" data-pane="open" aria-label="Reproducir ${esc(e.name)}">` +
               `<img alt="" src="${pic("thumb", p)}"><span class="sprite"></span><span class="scrub"></span>` +
               `<span class="play"><span class="ms fill">play_arrow</span></span>` +
               `${e.duration ? `<span class="dur">${fmtDur(e.duration)}</span>` : ""}</button>`;
      }
      return `<video controls playsinline preload="metadata" poster="${pic("thumb", p)}" src="${raw(p)}"></video>`;
    case "image": return `<img alt="${esc(e.name)}" src="${raw(p)}">`;
    case "audio": return `<audio controls preload="metadata" src="${raw(p)}"></audio>`;
    case "pdf": return `<iframe title="${esc(e.name)}" src="${raw(p)}"></iframe>`;
    case "text": return `<pre data-text="${esc(p)}">…</pre>`;
    default: return where === "viewer"
      ? `<div class="other"><span class="ms">${ICON[e.kind] || "draft"}</span><b>${esc(e.name)}</b><span>${fmtSize(e.size)}</span>` +
        `<a class="btn filled" href="${raw(p, true)}" download><span class="ms">download</span>Descargar</a></div>`
      : `<span class="ms${e.kind === "dir" ? " fill" : ""}">${ICON[e.kind] || "draft"}</span>`;
  }
}
function fillText(root) {
  $$("pre[data-text]", root).forEach(async pre => { pre.textContent = await textOf(pre.dataset.text); });
}

function renderPane() {
  const pane = $("#pane");
  if (!wide.matches) { pane.innerHTML = ""; return; }
  const e = entry(state.selected);
  if (!e) {
    const files = state.listing.entries.filter(x => x.kind !== "dir");
    const total = files.reduce((n, x) => n + (x.size || 0), 0);
    pane.innerHTML = `<div class="pane-empty"><div><span class="ms">touch_app</span>Elige un archivo para verlo aquí.<br>` +
      `<small>${count(state.listing.entries.length)}${files.length ? " · " + fmtSize(total) : ""}</small></div></div>`;
    return;
  }
  const rows = [];
  if (e.kind === "dir") rows.push(["Contiene", count(e.count || 0)]);
  else rows.push(["Tamaño", fmtSize(e.size)]);
  if (e.duration) rows.push(["Duración", fmtDur(e.duration)]);
  if (e.width) rows.push(["Calidad", `${quality(e)} · ${e.width}×${e.height}${e.vcodec ? " · " + e.vcodec.toUpperCase() : ""}`]);
  rows.push(["Fecha", fullFmt.format(new Date(e.mtime * 1000))]);
  const tall = e.kind === "pdf" || e.kind === "text";
  pane.innerHTML = `
    <div class="preview k-${e.kind}${tall ? " tall" : ""}">${stageHTML(e, "pane")}</div>
    <h2>${esc(e.name)}</h2>
    <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    <div class="buttons">
      ${e.kind === "dir"
        ? `<button class="btn outlined" data-pane="open"><span class="ms">folder_open</span>Abrir</button>
           <a class="btn tonal" href="/zip/${enc(pathOf(e))}" download><span class="ms">folder_zip</span>Descargar</a>`
        : `<button class="btn outlined" data-pane="open"><span class="ms">open_in_full</span>Abrir</button>
           <a class="btn tonal" href="${raw(pathOf(e), true)}" download><span class="ms">download</span>Descargar</a>`}
    </div>`;
  fillText(pane);
  wireThumbs(pane);
}
$("#pane").addEventListener("click", ev => {
  if (ev.target.closest('[data-pane="open"]')) open(entry(state.selected));
});
wide.addEventListener("change", renderPane);

/* ---------------------------------------------------------------- viewer */
const viewer = { list: [], i: 0 };
function openViewer(e) {
  viewer.list = state.items.filter(x => x.kind !== "dir");
  viewer.i = Math.max(0, viewer.list.findIndex(x => x.name === e.name));
  if ($("#viewer").hidden) history.pushState({ viewer: true }, "", location.href);
  $("#viewer").hidden = false;
  document.body.style.overflow = "hidden";
  $$("#pane video, #pane audio").forEach(m => m.pause());
  showViewer();
}
function showViewer() {
  const e = viewer.list[viewer.i];
  $("#v-name").textContent = e.name;
  $("#v-count").textContent = viewer.list.length > 1 ? `${viewer.i + 1} / ${viewer.list.length}` : "";
  $("#v-download").href = raw(pathOf(e), true);
  const stage = $("#v-stage");
  stage.innerHTML = stageHTML(e, "viewer");
  fillText(stage);
  stage.querySelector("video, audio")?.play().catch(() => {});
  $$(".viewer-nav").forEach(b => { b.hidden = viewer.list.length < 2; });
  if (wide.matches) select(e.name);
}
function moveViewer(d) {
  if (viewer.list.length < 2) return;
  viewer.i = (viewer.i + d + viewer.list.length) % viewer.list.length;
  showViewer();
}
function closeViewer(fromHistory) {
  $("#v-stage").innerHTML = "";
  $("#viewer").hidden = true;
  document.body.style.overflow = "";
  if (!fromHistory && history.state?.viewer) history.back();
  rowOf(state.selected)?.focus({ preventScroll: true });
}
$("#viewer").addEventListener("click", ev => {
  const b = ev.target.closest("[data-v]");
  if (b) return b.dataset.v === "close" ? closeViewer() : moveViewer(b.dataset.v === "next" ? 1 : -1);
  if (ev.target.id === "v-stage") closeViewer();
});
let touchX = null;
$("#viewer").addEventListener("touchstart", ev => { touchX = ev.touches.length === 1 ? ev.touches[0].clientX : null; }, { passive: true });
$("#viewer").addEventListener("touchend", ev => {
  if (touchX === null || ev.target.closest("video, audio, iframe, pre")) return;
  const dx = ev.changedTouches[0].clientX - touchX;
  if (Math.abs(dx) > 60) moveViewer(dx < 0 ? 1 : -1);
  touchX = null;
});

/* ---------------------------------------------------------------- toolbar */
let searchTimer;
$("#q").addEventListener("input", ev => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = ev.target.value; render(); }, 80);
});

function setView(view) {
  state.view = view;
  store.set("view", view);
  $("#list").classList.toggle("grid", view === "grid");
  $$(".seg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
  $("#viewtoggle .ms").textContent = view === "grid" ? "view_list" : "grid_view";
}
$$(".seg button").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
$("#viewtoggle").addEventListener("click", () => setView(state.view === "grid" ? "list" : "grid"));

function toggleSortMenu(force) {
  const menu = $("#sortmenu");
  const show = force ?? menu.hidden;
  menu.hidden = !show;
  if (!show) return;
  const r = $("#sort").getBoundingClientRect();
  menu.style.top = r.bottom + 4 + "px";
  menu.style.right = Math.max(8, innerWidth - r.right) + "px";
  $$("button", menu).forEach(b => b.setAttribute("aria-checked", String(b.dataset.sort === state.sort)));
  $(`[data-sort="${state.sort}"]`, menu).focus();
}
$("#sort").addEventListener("click", ev => { ev.stopPropagation(); toggleSortMenu(); });
$("#sortmenu").addEventListener("click", ev => {
  const b = ev.target.closest("[data-sort]");
  if (!b) return;
  state.sort = b.dataset.sort;
  store.set("sort", state.sort);
  toggleSortMenu(false);
  render();
});
document.addEventListener("click", ev => { if (!ev.target.closest("#sortmenu")) toggleSortMenu(false); });

/* ---------------------------------------------------------------- keyboard */
document.addEventListener("keydown", ev => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName);
  if (!$("#viewer").hidden) {
    if (ev.key === "Escape") closeViewer();
    else if (ev.key === "ArrowRight") moveViewer(1);
    else if (ev.key === "ArrowLeft") moveViewer(-1);
    return;
  }
  if (!$("#sortmenu").hidden && ev.key === "Escape") return toggleSortMenu(false);
  if ($("#shell").hidden || $("#mkdir-dialog").open) return;
  if (ev.key === "/" && !typing) { ev.preventDefault(); $("#q").focus(); return; }
  if (ev.key === "Escape" && document.activeElement === $("#q")) {
    if ($("#q").value) { $("#q").value = ""; state.query = ""; render(); } else $("#q").blur();
    return;
  }
  if (typing && !["ArrowDown", "Enter"].includes(ev.key)) return;
  const i = state.items.findIndex(e => e.name === state.selected);
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    ev.preventDefault();
    const next = state.items[Math.max(0, Math.min(state.items.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)))];
    if (next) select(next.name, true);
  } else if (ev.key === "Enter" && state.selected) {
    ev.preventDefault();
    open(entry(state.selected));
  } else if (ev.key === "Backspace" && !typing && state.dir) {
    go(state.dir.split("/").slice(0, -1).join("/"));
  }
});

/* ---------------------------------------------------------------- uploads */
function uploadFiles(files) {
  if (!state.info.uploads || !files.length) return;
  const dir = state.dir;
  const box = $("#uploads");
  let pending = files.length;
  const finish = () => { if (--pending === 0 && state.dir === dir) route(); };
  for (const f of files) {
    const el = document.createElement("div");
    el.className = "up";
    el.innerHTML = `<div class="n"><span>${esc(f.name)}</span><span>0 %</span></div><div class="bar"><i></i></div>`;
    box.append(el);
    const label = el.querySelector(".n span:last-child");
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/upload?dir=${encodeURIComponent(dir)}&name=${encodeURIComponent(f.name)}`);
    xhr.setRequestHeader("X-Wysun", "1");   // the server refuses writes a foreign page could forge
    xhr.upload.onprogress = ev => {
      if (!ev.lengthComputable) return;
      const pct = Math.round((ev.loaded / ev.total) * 100);
      el.querySelector("i").style.width = pct + "%";
      label.textContent = `${pct} % · ${fmtSize(ev.loaded)}`;
    };
    xhr.onload = () => {
      const ok = xhr.status === 200;
      el.classList.add(ok ? "done" : "err");
      el.querySelector("i").style.width = "100%";
      let error = "Error";
      try { error = JSON.parse(xhr.responseText).error || error; } catch { /* not JSON */ }
      label.textContent = ok ? "Listo" : error;
      setTimeout(() => el.remove(), ok ? 2500 : 6000);
      finish();
    };
    xhr.onerror = () => { el.classList.add("err"); label.textContent = "Se cortó la conexión"; setTimeout(() => el.remove(), 6000); finish(); };
    xhr.send(f);
  }
}
const pick = () => $("#picker").click();
$("#upload").addEventListener("click", pick);
$("#upload-fab").addEventListener("click", pick);
$("#picker").addEventListener("change", ev => { uploadFiles([...ev.target.files]); ev.target.value = ""; });

let dragDepth = 0;
const hasFiles = ev => [...(ev.dataTransfer?.types || [])].includes("Files");
addEventListener("dragenter", ev => {
  if (!hasFiles(ev) || !state.info?.uploads || $("#shell").hidden) return;
  dragDepth++;
  $("#drop-target").textContent = "en " + (state.dir ? state.dir.split("/").pop() : state.listing.title);
  $("#drop").classList.add("on");
});
addEventListener("dragover", ev => { if (hasFiles(ev)) ev.preventDefault(); });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#drop").classList.remove("on"); } });
addEventListener("drop", ev => {
  if (!hasFiles(ev)) return;
  ev.preventDefault();
  dragDepth = 0;
  $("#drop").classList.remove("on");
  if (state.info?.uploads) uploadFiles([...ev.dataTransfer.files]);
});

$("#mkdir").addEventListener("click", () => {
  $("#mkdir-name").value = "";
  $("#mkdir-dialog").showModal();
});
$("#mkdir-dialog").addEventListener("close", async () => {
  const dialog = $("#mkdir-dialog");
  const name = $("#mkdir-name").value.trim();
  if (dialog.returnValue !== "ok" || !name) return;
  try {
    await api(`/api/mkdir?dir=${encodeURIComponent(state.dir)}&name=${encodeURIComponent(name)}`, { method: "POST", headers: { "X-Wysun": "1" } });
    toast("Carpeta creada");
    route();
  } catch (err) {
    if (err.message !== "locked") toast(err.message);
  }
});

start();
