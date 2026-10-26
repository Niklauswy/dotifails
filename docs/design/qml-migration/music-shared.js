/* Wysun Music · maquetas — núcleo: formas expresivas, carátulas, datos de ejemplo, navegación adaptable,
   minirreproductor, controles de la página e interacciones mínimas. Los contenidos de cada pantalla están en music-screens.js. */
(function () {
  const MX = (window.MX = {});

  /* ---------- Formas M3 Expressive: polígonos de 96 vértices (misma topología → clip-path se transforma) ---------- */
  const N = 96;
  function poly(fn) {
    const pts = [];
    for (let i = 0; i < N; i++) {
      const t = (i / N) * Math.PI * 2, r = fn(t);
      pts.push((50 + 50 * r * Math.cos(t - Math.PI / 2)).toFixed(2) + '% ' + (50 + 50 * r * Math.sin(t - Math.PI / 2)).toFixed(2) + '%');
    }
    return 'polygon(' + pts.join(',') + ')';
  }
  const lobes = (k, a, p = 1) => (t) => (1 / (1 + a)) * (1 + a * Math.sign(Math.cos(k * t)) * Math.pow(Math.abs(Math.cos(k * t)), p));
  MX.shapes = {
    circle: poly(() => 1),
    cookie: poly(lobes(9, 0.07)),           // cookie de 9 lados
    sunny: poly(lobes(8, 0.1, 0.55)),       // «sunny»
    clover: poly(lobes(4, 0.16)),           // trébol de 4
    flower: poly(lobes(6, 0.14)),
    squircle: poly((t) => 1 / Math.pow(Math.pow(Math.abs(Math.cos(t)), 4) + Math.pow(Math.abs(Math.sin(t)), 4), 0.25) * 0.985),
    softburst: poly(lobes(12, 0.045)),
  };

  /* ---------- Carátulas generadas (contenido: los colores no pertenecen al tema) ---------- */
  const hsl = (h, s, l) => `hsl(${((h % 360) + 360) % 360} ${s}% ${l}%)`;
  MX.art = function (seed) {
    const h = (seed * 47 + 13) % 360, k = seed % 5;
    if (k === 0) return `linear-gradient(135deg, ${hsl(h, 72, 52)}, ${hsl(h + 70, 78, 28)}), radial-gradient(circle at 30% 25%, ${hsl(h + 30, 90, 70)}, transparent 60%)`;
    if (k === 1) return `conic-gradient(from ${seed * 30}deg at 55% 45%, ${hsl(h, 70, 55)}, ${hsl(h + 80, 65, 38)}, ${hsl(h + 150, 70, 60)}, ${hsl(h, 70, 55)})`;
    if (k === 2) return `radial-gradient(circle at 50% 120%, ${hsl(h + 20, 90, 62)} 0 30%, transparent 31%), linear-gradient(180deg, ${hsl(h + 200, 55, 20)}, ${hsl(h, 70, 42)})`;
    if (k === 3) return `repeating-linear-gradient(60deg, ${hsl(h, 60, 46)} 0 14px, ${hsl(h + 40, 60, 34)} 14px 28px)`;
    return `radial-gradient(circle at 70% 30%, ${hsl(h + 50, 95, 75)} 0 14%, transparent 15%), linear-gradient(160deg, ${hsl(h, 55, 36)}, ${hsl(h - 40, 70, 22)})`;
  };
  // opts: shape (clave de MX.shapes), r ('s'|'l'|'xl'|'round'), glyph (texto o icono), cls, style
  MX.cover = function (seed, o = {}) {
    const shaped = o.shape ? ' shaped' : '';
    const rad = !o.shape && o.r ? ' ' + (o.r === 'round' ? 'round' : 'sq-' + o.r) : '';
    const glyph = o.glyph ? `<span class="glyph ${o.icon ? 'ms fill' : ''}" style="${o.gs || ''}">${o.glyph}</span>` : '';
    const st = `background:${MX.art(seed)};${o.shape ? `--shape:${MX.shapes[o.shape]};` : ''}${o.style || ''}`;
    return `<div class="cover${shaped}${rad} ${o.cls || ''}" style="${st}" ${o.attrs || ''}>${glyph}</div>`;
  };
  const ms = (n, f, c = '') => `<span class="ms ${f ? 'fill' : ''} ${c}">${n}</span>`;
  MX.ms = ms;

  /* ---------- Datos de ejemplo (ficticios) ---------- */
  MX.albums = [
    ['Mar de fondo', 'Lucía Aranda', 2024], ['Noches de neón', 'Los Cuarzo', 2023], ['Cartas sin enviar', 'Mateo Brisa', 2022],
    ['Desierto azul', 'Ámbar Vega', 2024], ['Fiebre de domingo', 'Nube Norte', 2021], ['Tierra mojada', 'Lucía Aranda', 2020],
    ['Casa de cristal', 'Orquesta Marea', 2019], ['Cometas', 'Los Cuarzo', 2025], ['Pausa', 'Iris Montoya', 2023],
    ['Radio nocturna', 'Nube Norte', 2022], ['Sal y sol', 'Ámbar Vega', 2021], ['Hilo rojo', 'Iris Montoya', 2025],
  ].map((a, i) => ({ id: i, t: a[0], a: a[1], y: a[2], seed: i + 1 }));
  MX.artists = [['Lucía Aranda', 42, 'LA'], ['Los Cuarzo', 31, 'LC'], ['Mateo Brisa', 18, 'MB'], ['Ámbar Vega', 27, 'ÁV'], ['Nube Norte', 24, 'NN'], ['Iris Montoya', 19, 'IM'],
    ['Orquesta Marea', 12, 'OM'], ['Cecilia Ñandú', 9, 'CÑ']].map((a, i) => ({ n: a[0], c: a[1], ini: a[2], seed: i + 20, shape: ['cookie', 'sunny', 'flower', 'clover', 'softburst', 'cookie', 'sunny', 'flower'][i] }));
  MX.tracks = [
    ['Marea baja', 'Lucía Aranda', 'Mar de fondo', '3:42'], ['Faro', 'Lucía Aranda', 'Mar de fondo', '4:05'], ['Sal en la piel', 'Lucía Aranda, Mateo Brisa', 'Mar de fondo', '3:18'],
    ['Corriente', 'Lucía Aranda', 'Mar de fondo', '2:57'], ['Ola larga', 'Lucía Aranda', 'Mar de fondo', '5:11'], ['Bahía', 'Lucía Aranda', 'Mar de fondo', '3:33'],
    ['Costa (feat. Iris Montoya)', 'Lucía Aranda', 'Mar de fondo', '4:20'], ['Espuma', 'Lucía Aranda', 'Mar de fondo', '2:48'], ['Último muelle', 'Lucía Aranda', 'Mar de fondo', '3:59'],
    ['Mar de fondo', 'Lucía Aranda', 'Mar de fondo', '6:02'],
  ].map((t, i) => ({ n: i + 1, t: t[0], a: t[1], al: t[2], d: t[3], seed: 1 }));
  MX.playlists = [['Mi playlist n.º 1', 'user', 31], ['Para correr', 'user', 22], ['Selección 1', 'spotify', 80], ['Cenas con ruido', 'user', 14]];

  /* ---------- Navegación: rail / drawer / modal desde los mismos destinos ---------- */
  const NAV_LISTEN = [['home', 'home', 'Inicio', 'M-10'], ['search', 'explore', 'Explorar', 'M-16'], ['downloads', 'download', 'Añadir música', 'M-62']];
  const NAV_LIB = [['songs', 'music_note', 'Canciones'], ['artists', 'artist', 'Artistas'], ['albums', 'album', 'Álbumes'], ['recent', 'history', 'Recientes'], ['favorites', 'favorite', 'Tus me gusta']];
  const RAIL = [['home', 'home', 'Inicio'], ['search', 'explore', 'Explorar'], ['lib', 'library_music', 'Biblioteca'], ['lists', 'queue_music', 'Listas'], ['downloads', 'download', 'Añadir']];
  const railKey = (r) => ({ home: 'home', search: 'search', downloads: 'downloads' }[r] || (r.startsWith('pl') ? 'lists' : 'lib'));
  const item = (r, route, icon, label, extra = '') => `<div class="item sl ${route === r ? 'on' : ''}" data-route="${r}">${ms(icon, route === r)}${label}${extra}</div>`;
  function navItems(route) {
    const mk = (r, i, l, m) => `<div class="item sl ${route === r ? 'on' : ''}" ${m ? `data-m="${m}"` : ''}>${ms(i, route === r)}${l}</div>`;
    return `<div class="head">Escuchar</div>` + NAV_LISTEN.map((n) => mk(n[0], n[1], n[2], n[3])).join('') +
      `<div class="head">Biblioteca</div>` + NAV_LIB.map((n, i) => mk(n[0], n[1], n[2], i === 0 ? 'M-10' : i === 3 ? 'M-40' : '')).join('') +
      `<div class="head" data-m="M-11">Playlists<span class="iconbtn sl" title="Nueva playlist · Ctrl+N" style="margin-left:auto">${ms('add')}</span></div>` +
      MX.playlists.slice(0, 3).map((p, i) => `<div class="item small sl ${route === 'pl' + i ? 'on' : ''}" ${i === 0 ? 'data-m="M-12"' : ''}>${MX.cover(60 + i, { r: 's', cls: 'mini' })}<span class="ell">${p[0]}</span>${i === 1 ? `<span class="eq"><span class="eqbars">${'<i></i>'.repeat(3)}</span></span>` : ''}</div>`).join('');
  }
  function nav(route) {
    const rk = railKey(route);
    const rail = `<nav class="rail"><div class="menu-btn-r">${ms('menu')}</div><div class="fab" title="Nueva playlist · Ctrl+N" data-m="M-11">${ms('playlist_add')}</div>` +
      RAIL.map((n) => `<div class="item ${rk === n[0] ? 'on' : ''}"><div class="ind sl">${ms(n[1], rk === n[0])}</div>${n[2]}</div>`).join('') +
      `<div class="spacer"></div><div class="item"><div class="ind sl">${ms('keyboard')}</div>Atajos</div></nav>`;
    const fab = `<div class="fab">${ms('playlist_add')}Nueva playlist</div>`;
    const drawer = `<nav class="drawer">${fab}${navItems(route)}</nav>`;
    const modal = `<div class="scrim" data-act="close-nav"></div><nav class="modal">${fab}${navItems(route)}</nav>`;
    return rail + drawer + modal;
  }

  /* ---------- Barra superior: atrás/adelante, búsqueda global, ocultar, atajos ---------- */
  MX.topbar = function (o = {}) {
    const typed = o.typed ? `<span class="typed">${o.typed}</span>` : `<span>Buscar en tu biblioteca</span>`;
    return `<header class="topbar">
      <span class="iconbtn sl menu-btn" data-act="open-nav" title="Menú">${ms('menu')}</span>
      <span class="iconbtn sl hide-compact" data-m="M-03" title="Ocultar · la música sigue sonando">${ms('close')}</span>
      <span class="iconbtn sl" data-m="M-13" title="Atrás · Alt+←">${ms('chevron_left')}</span>
      <span class="iconbtn sl hide-compact" ${o.noForward ? 'disabled' : ''} title="Adelante · Alt+→">${ms('chevron_right')}</span>
      <div class="search ${o.focus ? 'focus' : ''}" data-m="M-15">${ms(o.focus ? 'arrow_back' : 'search')}${typed}${o.focus ? ms('close') : '<kbd data-m="M-18">Ctrl K</kbd>'}</div>
      <span class="iconbtn sl hide-compact" data-m="M-22" title="Atajos de teclado · F1">${ms('keyboard')}</span>
    </header>`;
  };

  /* ---------- Onda de progreso (M3 Expressive: la parte reproducida ondula; en pausa se aplana) ---------- */
  MX.wave = function (pct = 0.4, playing = true) {
    const W = 300, x1 = W * pct, amp = playing ? 3.2 : 0, k = 0.33;
    let d = '';
    for (let x = -24; x <= x1; x += 2) d += (x === -24 ? 'M' : 'L') + x + ' ' + (7 + amp * Math.sin(x * k)).toFixed(2) + ' ';
    const id = 'w' + Math.random().toString(36).slice(2, 7), L = ((Math.PI * 2) / k).toFixed(3);
    return `<svg viewBox="0 0 ${W} 14" preserveAspectRatio="none" aria-hidden="true"><defs><clipPath id="${id}"><rect x="0" y="-4" width="${x1}" height="22"/></clipPath></defs>
      <line x1="${x1}" y1="7" x2="${W}" y2="7" stroke="var(--m3-outline-variant)" stroke-width="4" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
      <g clip-path="url(#${id})"><path d="${d}" fill="none" stroke="var(--m3-primary)" stroke-width="4" stroke-linecap="round" vector-effect="non-scaling-stroke">${playing ? `<animateTransform attributeName="transform" type="translate" from="0" to="${-L}" dur="1.2s" repeatCount="indefinite"/>` : ''}</path></g>
      <rect x="${x1 - 2}" y="-2" width="4" height="18" rx="2" fill="var(--m3-primary)"/></svg>`;
  };

  /* ---------- Cápsula del reproductor ---------- */
  MX.player = function (o = {}) {
    const playing = o.playing !== false, empty = o.empty;
    const cur = empty ? null : (o.track || { t: 'Marea baja', a: 'Lucía Aranda' });
    return `<footer class="player" data-m="M-45">
      <div class="now">${empty ? MX.cover(0, { shape: 'cookie', cls: 'idle', style: 'background:var(--m3-sc-low)', glyph: 'music_note', icon: 1, gs: 'color:var(--m3-on-surface-variant)' })
        : `<div class="${playing ? 'spin' : ''}" style="display:contents">${MX.cover(1, { shape: playing ? 'cookie' : 'circle', attrs: 'data-act="cover" data-m="M-49" title="Abrir Ahora suena · Ctrl+P"' })}</div>`}
        <div class="tt grow"><b class="ell">${empty ? 'Nada sonando' : cur.t}</b><span class="ell">${empty ? 'Elige una canción' : cur.a}</span></div>
        ${empty ? '' : `<span class="iconbtn sl heart-btn on" data-act="heart" data-m="M-39" title="Guardar en Tus me gusta · Ctrl+Shift+F" style="color:var(--m3-tertiary)">${ms('favorite', 1)}</span>`}</div>
      <div class="center"><div class="transport">
        <span class="iconbtn sl opt" data-m="M-48" title="Aleatorio · Ctrl+S">${ms('shuffle')}</span>
        <span class="iconbtn sl" title="Anterior · Ctrl+←">${ms('skip_previous', 1)}</span>
        <button class="playbtn ${playing ? 'playing' : ''}" data-act="play" ${empty ? 'disabled' : ''} title="Reproducir · Espacio">${ms(playing ? 'pause' : 'play_arrow', 1, 's32')}</button>
        <span class="iconbtn sl" title="Siguiente · Ctrl+→">${ms('skip_next', 1)}</span>
        <span class="iconbtn sl opt on" title="Repetir lista · Ctrl+R" style="background:transparent;color:var(--m3-primary)">${ms('repeat')}</span></div>
        <div class="progress" data-m="M-46"><span class="time">1:24</span><div class="wave">${MX.wave(empty ? 0 : 0.38, playing && !empty)}</div><span class="time">3:42</span></div></div>
      <div class="tools"><span class="iconbtn sl on" data-m="M-50" title="Letra · Ctrl+L">${ms('lyrics')}</span><span class="iconbtn sl" title="Cola · Ctrl+Q">${ms('queue_music')}</span>
        <span class="iconbtn sl" data-m="M-47" title="Silenciar · M">${ms('volume_up')}</span><div class="vol"><i></i><b></b></div></div>
    </footer>`;
  };

  /* ---------- Ventana ---------- */
  // o: route, content, id, width (px), cls, search{typed,focus}, player{...}|false, overlay (html), navOpen
  MX.win = function (o) {
    return `<div class="m3 ${o.fixed ? 'fixed' : ''}" data-palette="${o.palette || 'grafito'}" data-mode="${o.mode || 'dark'}">
      <div class="win ${o.cls || ''} ${o.navOpen ? 'nav-open' : ''}" id="${o.id || ''}" style="${o.width ? `width:${o.width}px` : 'width:100%'}">
        ${nav(o.route)}
        <div class="main">${MX.topbar(o.search || {})}<div class="content ${o.pad0 ? 'pad0' : ''}">${o.content}</div>
          ${o.player === false ? '' : MX.player(o.player || {})}${o.snack ? `<div class="snack">${o.snack}</div>` : ''}${o.floating || ''}</div>
        ${o.overlay || ''}
      </div></div>`;
  };

  /* ---------- Controles de la página ---------- */
  MX.controls = function (pages, current) {
    const links = pages.map((p) => `<a href="${p[0]}" ${p[0] === current ? 'style="font-weight:700;opacity:1;text-decoration:underline"' : ''}>${p[1]}</a>`).join('');
    const btn = (g, v, t, on) => `<button data-g="${g}" data-v="${v}" aria-pressed="${!!on}">${t}</button>`;
    return `<div class="ctrl"><div class="grp">${links}</div>
      <div class="grp"><span>Paleta</span>${btn('palette', 'grafito', 'Grafito (tu wallpaper)', 1)}${btn('palette', 'indigo', 'Índigo')}${btn('palette', 'ambar', 'Ámbar')}${btn('palette', 'salvia', 'Salvia')}</div>
      <div class="grp"><span>Modo</span>${btn('mode', 'dark', 'Oscuro', 1)}${btn('mode', 'light', 'Claro')}</div>
      <div class="grp"><span>Ancho</span>${btn('width', '400', 'Compacto 400')}${btn('width', '720', 'Medio 720')}${btn('width', '1040', 'Amplio 1040', 1)}</div>
      <div class="grp"><span>Paridad</span>${btn('parity', 'on', 'Mostrar IDs M-xx')}</div></div>`;
  };

  /* ---------- Interacción ---------- */
  function setAll(attr, val) { document.querySelectorAll('.m3:not(.fixed)').forEach((e) => e.setAttribute(attr, val)); }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.ctrl button');
    if (b) {
      const g = b.dataset.g, v = b.dataset.v;
      if (g === 'parity') { const on = document.body.classList.toggle('parity'); b.setAttribute('aria-pressed', on); return; }
      b.parentElement.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', x === b));
      if (g === 'palette') setAll('data-palette', v);
      if (g === 'mode') { setAll('data-mode', v); document.body.classList.toggle('page-light', v === 'light'); }
      if (g === 'width') document.querySelectorAll('.win.wvar').forEach((w) => (w.style.width = v + 'px'));
      return;
    }
    const a = e.target.closest('[data-act]');
    const win = e.target.closest('.win');
    if (a && win) {
      const act = a.dataset.act;
      if (act === 'open-nav') win.classList.add('nav-open');
      if (act === 'close-nav') win.classList.remove('nav-open');
      if (act === 'play') {
        const on = a.classList.toggle('playing');
        a.innerHTML = ms(on ? 'pause' : 'play_arrow', 1, a.classList.contains('lg') ? 's48' : 's32');
        win.querySelectorAll('.cover[data-act="cover"]').forEach((c) => { c.style.setProperty('--shape', MX.shapes[on ? 'cookie' : 'circle']); });
      }
      if (act === 'heart') { a.classList.toggle('on'); a.firstChild.classList.toggle('fill'); a.style.color = a.classList.contains('on') ? 'var(--m3-tertiary)' : ''; }
      return;
    }
    const tab = e.target.closest('.tabs .tab');
    if (tab) { tab.parentElement.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t === tab)); const sec = tab.closest('[data-tabs]'); if (sec) MX.onTab && MX.onTab(sec, tab.dataset.tab); return; }
    const chip = e.target.closest('.chips .chip[data-toggle]');
    if (chip) { chip.classList.toggle('on'); return; }
    const row = e.target.closest('.trow:not(.head)');
    if (row && !e.target.closest('.iconbtn')) { row.classList.toggle('sel'); return; }
  });
  MX.init = function () {
    document.querySelectorAll('.m3-fixed-init').forEach((e) => e.remove());
  };
})();
