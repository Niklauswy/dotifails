/* Wysun Music · maquetas — contenido de cada pantalla. Cada elemento con data-m="M-xx" corresponde a una fila de
   docs/superpowers/specs/2026-10-26-qml-paridad-music-files.md (botón «Mostrar IDs» de la barra superior). */
(function () {
  const MX = window.MX, ms = MX.ms, S = (MX.screens = {});
  const A = MX.albums, AR = MX.artists, T = MX.tracks;
  const NEW = (t = 'nueva') => `<span class="note-new">${t}</span>`;

  const alb = (a, o = {}) => `<div class="album ${o.sel ? 'sel' : ''}" ${o.m ? `data-m="${o.m}"` : ''}>${o.sel ? `<span class="sel-check">${ms('check', 0, 's18')}</span>` : ''}${MX.cover(a.seed, { shape: o.shape || null, r: 'l' })}
    <span class="play">${ms('play_arrow', 1)}</span><b class="ell">${a.t}</b><span class="ell">${o.sub || a.a + ' · ' + a.y}</span></div>`;
  const art = (a, o = {}) => `<div class="album artist ${o.sel ? 'sel' : ''}">${MX.cover(a.seed, { shape: a.shape, glyph: a.ini, gs: 'font-size:30px;letter-spacing:.02em' })}<span class="play" style="top:80px">${ms('play_arrow', 1)}</span><b class="ell" style="text-align:center">${a.n}</b><span>${a.c} canciones</span></div>`;
  const mosaic = (s) => `<div class="mosaic">${[0, 1, 2, 3].map((i) => MX.cover(s + i * 3, { r: 's' })).join('')}</div>`;
  const shelf = (title, sub, inner, m, more = 'Ver todo') => `<div class="shelf-h" ${m ? `data-m="${m}"` : ''}><h3>${title}</h3>${sub ? `<span>${sub}</span>` : ''}<a>${more}</a></div><div class="shelf">${inner}</div>`;

  /* ---------------- Inicio ---------------- */
  S.home = () => `<div class="greet" data-m="M-19"><h2>Buenas tardes</h2><p>3 132 canciones disponibles · 8 playlists</p></div>
    <div class="bento">
      <div class="bt resume" data-m="M-19">${MX.cover(1, { shape: 'cookie', cls: 'spin' })}<span class="eyebrow">Sonando ahora</span><b>Marea baja</b><span class="s">Lucía Aranda · Mar de fondo</span>
        <div class="btnrow"><span class="btn filled">${ms('pause', 1)}Pausar</span><span class="btn tonal">${ms('lyrics')}Letra</span></div></div>
      <div class="bt liked"><div class="deco" style="--shape:${MX.shapes.sunny}">${ms('favorite', 1)}</div><span class="eyebrow">Colección</span><b>Tus me gusta</b><span class="s">412 canciones</span></div>
      <div class="bt mix"><div class="deco" style="--shape:${MX.shapes.clover}">${ms('shuffle')}</div><span class="eyebrow">Para ti</span><b>Mezcla</b><span class="s">Toda tu biblioteca, al azar</span></div>
      <div class="bt wide" style="background:var(--m3-sc-high)"><div class="deco" style="--shape:${MX.shapes.flower};color:var(--m3-primary)">${ms('history')}</div><span class="eyebrow">Recientes</span><b>Lo último que escuchaste</b><span class="s">Mar de fondo · Cometas · Pausa</span></div>
    </div>
    ${shelf('Escuchado recientemente', '', A.slice(0, 7).map((a, i) => alb(a, { shape: i === 0 ? 'squircle' : null })).join(''), 'M-40')}
    ${shelf('Tus playlists', 'Listas que guardaste o creaste', MX.playlists.map((p, i) => `<div class="poster">${mosaic(30 + i * 4)}<b class="ell">${p[0]}</b><span>${p[2]} canciones</span>${p[1] === 'spotify' ? `<br><span class="badge">${ms('open_in_new', 0, 's18')} Spotify</span>` : ''}</div>`).join(''), 'M-11')}
    <div class="shelf-h" data-m="M-19"><h3>Lo que más escuchas</h3><span>Tus canciones más reproducidas</span></div>
    <div class="rank">${T.slice(0, 6).map((t, i) => `<div class="rr"><span class="n">${i + 1}</span>${MX.cover(2 + i, { r: 's' })}<div class="grow"><b class="ell">${t.t}</b><span class="a ell">${t.a.split(',')[0]}</span></div></div>`).join('')}</div>
    ${shelf('Álbumes', '', A.slice(2, 9).map((a) => alb(a)).join(''), '')}
    ${shelf('Tus artistas', '', AR.map((a) => art(a)).join(''), 'M-26')}`;

  /* ---------------- Biblioteca (pestañas) ---------------- */
  const sortChip = `<span class="chip" data-m="M-29">${ms('sort')}Orden personalizado${ms('arrow_drop_down')}</span>`;
  S.library = (tab = 'albums', o = {}) => {
    const head = `<div class="libhead"><h2>Biblioteca</h2><span class="count">${{ albums: '134 álbumes', artists: '86 artistas', songs: '3 132 canciones', lists: '8 listas' }[tab]}</span></div>
      <div data-tabs="lib"><div class="tabs" data-m="M-10"><div class="tab ${tab === 'albums' ? 'on' : ''}" data-tab="albums">${ms('album', 0, 's20')}Álbumes</div><div class="tab ${tab === 'artists' ? 'on' : ''}" data-tab="artists">${ms('artist', 0, 's20')}Artistas</div>
        <div class="tab ${tab === 'songs' ? 'on' : ''}" data-tab="songs">${ms('music_note', 0, 's20')}Canciones</div><div class="tab ${tab === 'lists' ? 'on' : ''}" data-tab="lists">${ms('queue_music', 0, 's20')}Listas</div></div></div>
      <div class="libbar"><div class="chips"><span class="chip on" data-toggle>${ms('check')}Todo</span><span class="chip" data-toggle data-m="M-40">${ms('history', 0, 's18')}Recientes</span><span class="chip" data-toggle>${ms('favorite', 0, 's18')}Tus me gusta</span></div><span class="sp"></span>${sortChip}</div>`;
    let body = '';
    if (tab === 'albums') body = `<div class="grid" data-m="M-20">${A.concat(A).slice(0, 18).map((a, i) => alb(a, { sel: o.selectAlbums && i < 2, shape: null })).join('')}</div>`;
    if (tab === 'artists') body = `<div class="grid artists" data-m="M-20">${AR.concat(AR).slice(0, 14).map((a, i) => art(a, { sel: o.selectAlbums && i < 2 })).join('')}</div>`;
    if (tab === 'songs') body = S.trows(T, { album: true, covers: true, sel: o.sel, select: o.select, cur: 0, hearts: [0, 3] });
    if (tab === 'lists') body = `<div class="smart"><div class="sc" style="background:var(--m3-tertiary-container);color:var(--m3-on-tertiary-container)"><div class="shape" style="--shape:${MX.shapes.sunny};background:color-mix(in oklab,currentColor 16%,transparent)">${ms('favorite', 1)}</div>Tus me gusta</div>
        <div class="sc" style="background:var(--m3-secondary-container);color:var(--m3-on-secondary-container)" data-m="M-40"><div class="shape" style="--shape:${MX.shapes.softburst};background:color-mix(in oklab,currentColor 16%,transparent)">${ms('history')}</div>Recientes</div></div>
      <div class="cards-grid">${MX.playlists.concat([['Selección 2', 'spotify', 60], ['Domingo lento', 'user', 18]]).map((p, i) => `<div class="pl-card" ${i === 0 ? 'data-m="M-38"' : ''}>${mosaic(40 + i * 4)}<div class="grow"><b class="ell">${p[0]}</b><span>${p[2]} canciones${p[1] === 'spotify' ? ' <span class="tag">' + ms('open_in_new', 0, 's18') + 'Spotify</span>' : ''}</span></div><span class="play">${ms('play_arrow', 1)}</span></div>`).join('')}</div>`;
    return head + body;
  };

  /* ---------------- Filas de canciones ---------------- */
  // o: album (columna), covers, sel (índices), select (modo selección con casillas), cur (índice sonando), hearts
  S.trows = (list, o = {}) => {
    const sel = o.sel || [], hearts = o.hearts || [];
    const head = `<div class="trow head ${o.album === false ? 'no-album' : ''}" ${o.select ? '' : ''}><span style="text-align:center">${o.select ? '' : '#'}</span><span></span><span>Título</span><span class="artistcol">Artista</span>${o.album === false ? '' : '<span class="albumcol">Álbum</span>'}<span class="dur-col" style="text-align:right">${ms('schedule', 0, 's18')}</span><span></span></div>`;
    const rows = list.map((t, i) => {
      const isSel = sel.includes(i), cur = o.cur === i;
      const first = o.select ? `<span class="chk">${isSel ? ms('check', 0, 's18') : ''}</span>` : cur ? `<span class="eqbars" style="margin:auto">${'<i></i>'.repeat(3)}</span>` : `<span class="num">${t.n}</span>`;
      return `<div class="trow ${i % 2 ? 'alt' : ''} ${isSel ? 'sel' : ''} ${cur ? 'cur' : ''} ${o.album === false ? 'no-album' : ''}" ${i === 0 ? 'data-m="M-32"' : ''}>${first}${o.covers === false ? '<span></span>' : MX.cover(1 + (t.n % 5) + (o.seed || 0), { r: 's' })}
        <div class="t"><b class="ell">${t.t}</b><span class="ell" style="display:none"></span></div><span class="m artistcol ell">${t.a}</span>${o.album === false ? '' : `<span class="m albumcol ell">${t.al}</span>`}
        <span class="dur dur-col">${t.d}</span><div class="acts"><span class="iconbtn sl heart ${hearts.includes(i) ? 'on' : ''}" data-act="heart">${ms('favorite', hearts.includes(i))}</span><span class="iconbtn sl">${ms('more_horiz')}</span></div></div>`;
    }).join('');
    return `<div class="tracks">${head}${rows}</div>`;
  };

  /* ---------------- Colecciones ---------------- */
  const actions = (o = {}) => `<div class="actions"><span class="btn filled lg" data-m="M-28">${ms('play_arrow', 1)}Reproducir</span><span class="btn tonal lg">${ms('shuffle')}Aleatorio</span>
      <span class="iconbtn tonal sl" style="width:56px;height:56px" data-m="M-37" title="Más opciones">${ms('more_horiz')}</span>
      <div class="filter" data-m="M-29">${ms('filter_list')}Buscar en la lista</div><span class="iconbtn sl" title="Ordenar">${ms('sort')}</span></div>`;
  S.collection = (kind = 'album', o = {}) => {
    const al = A[0], tracks = T;
    const cover = {
      album: MX.cover(al.seed, { shape: 'squircle', attrs: 'data-m="M-25"' }),
      artist: MX.cover(AR[0].seed, { shape: 'cookie', glyph: 'LA', gs: 'font-size:64px', attrs: 'data-m="M-26"' }),
      user: `<div class="cover" style="aspect-ratio:1;display:grid;grid-template-columns:1fr 1fr;gap:2px;background:none;border-radius:var(--rounding-xl);clip-path:none">${[0, 1, 2, 3].map((i) => MX.cover(50 + i, { r: 's', style: 'width:100%;border-radius:0' })).join('')}</div>`,
      favorites: MX.cover(0, { shape: 'sunny', style: 'background:var(--m3-tertiary-container)', glyph: 'favorite', icon: 1, gs: 'font-size:84px;color:var(--m3-on-tertiary-container)' }),
      recent: MX.cover(0, { shape: 'softburst', style: 'background:var(--m3-primary-container)', glyph: 'history', icon: 1, gs: 'font-size:84px;color:var(--m3-on-primary-container)' }),
    }[kind];
    const info = {
      album: ['Álbum', 'Mar de fondo', 'Lucía Aranda', '10 canciones · 38 min · 2024'], artist: ['Artista', 'Lucía Aranda', '4 álbumes', '42 canciones · 2 h 31 min'],
      user: ['Playlist', 'Mi playlist n.º 1', 'Tu playlist', '31 canciones · 1 h 54 min · Actualizado hoy'], favorites: ['Colección', 'Tus me gusta', 'Guardadas por ti', '412 canciones · 26 h'],
      recent: ['Colección', 'Escuchado recientemente', 'Tus últimas canciones', '50 canciones · 3 h 10 min'],
    }[kind];
    const wash = `<div class="wash" data-m="M-27" style="background:${kind === 'favorites' ? 'var(--m3-tertiary-container)' : kind === 'recent' ? 'var(--m3-primary-container)' : MX.art(al.seed)}"></div>`;
    const hero = `${wash}<div class="hero" data-m="M-25">${cover}<div class="info"><div class="kind">${info[0]}</div><h2 class="ell" style="white-space:normal">${info[1]}</h2><div class="by">${info[2]}</div><div class="meta">${info[3]}</div></div></div>`;
    let body;
    if (kind === 'artist') {
      body = actions() + `<div class="shelf-h" style="margin-top:6px"><h3>Álbumes</h3><span>Lucía Aranda · 4 álbumes</span></div><div class="shelf">${[A[0], A[5], A[3], A[8]].map((a) => alb(a)).join('')}</div><div class="shelf-h"><h3>Canciones</h3><span>incluye colaboraciones</span></div>` + S.trows(tracks.slice(0, 6), { album: true, cur: 0, hearts: [1] });
    } else body = actions() + S.trows(tracks, { album: kind !== 'album', covers: kind !== 'album', cur: kind === 'album' ? 0 : 2, hearts: [0, 3, 4], sel: o.sel, select: o.select });
    return hero + body;
  };

  /* Menús / diálogos (posicionados sobre la ventana) */
  const mi = (icon, label, key = '', cls = '') => `<div class="mi ${cls}">${icon ? ms(icon) : '<span style="width:24px"></span>'}${label}${key ? `<span class="key">${key}</span>` : ''}</div>`;
  S.trackMenu = (style = 'left:300px;top:250px') => `<div class="menu floating" style="${style}" data-m="M-35">
    ${mi('play_arrow', 'Reproducir', 'Enter')}${mi('playlist_play', 'Reproducir a continuación')}${mi('queue_music', 'Añadir a la cola')}<hr>
    ${mi('playlist_add', 'Añadir a playlist', '▸', 'hl')}${mi('playlist_remove', 'Quitar de esta playlist')}${mi('favorite', 'Guardar en Tus me gusta', 'F')}<hr>
    ${mi('artist', 'Ir al artista', 'Ctrl Enter')}${mi('folder_open', 'Mostrar en la carpeta')}</div>
    <div class="menu floating" style="${style.replace(/left:(\d+)px/, (m, x) => 'left:' + (+x + 250) + 'px')};min-width:200px;top:calc(${style.match(/top:(\d+)px/)[1]}px + 168px)">${mi('add', 'Nueva playlist…', 'Ctrl N')}<hr>${mi('', 'Mi playlist n.º 1')}${mi('', 'Para correr')}${mi('', 'Cenas con ruido')}</div>`;
  S.collectionMenu = (style = 'left:260px;top:318px') => `<div class="menu floating" style="${style}" data-m="M-37">${mi('play_arrow', 'Reproducir')}${mi('shuffle', 'Reproducir en aleatorio')}${mi('queue_music', 'Añadir a la cola')}<hr>
    ${mi('drive_file_rename_outline', 'Cambiar nombre…')}${mi('delete', 'Eliminar playlist', '', 'danger')}<hr>${mi('open_in_new', 'Abrir en Spotify')}</div>`;
  S.dlgNew = () => `<div class="overlay"><div class="dialog" data-m="M-38"><h4>Nueva playlist</h4><div class="field focus"><label>Nombre</label>Mi playlist n.º 2<span style="margin-left:auto" class="ms">close</span></div>
    <div class="acts"><span class="btn text">Cancelar</span><span class="btn filled">Crear</span></div></div></div>`;
  S.dlgDelete = () => `<div class="overlay"><div class="dialog" data-m="M-38">${ms('delete', 1, 's32 ico')}<h4 style="text-align:center">¿Eliminar «Mi playlist n.º 1»?</h4><p style="text-align:center">Las canciones siguen en tu biblioteca.</p>
    <div class="acts"><span class="btn text">Cancelar</span><span class="btn danger tonal" style="background:var(--m3-error-container)">Eliminar</span></div></div></div>`;
  S.selbar = (n = 3) => `<div class="selbar" data-m="M-33"><span class="iconbtn sl" title="Salir de la selección">${ms('close')}</span><b>${n} seleccionadas</b>
    <span class="iconbtn sl" title="Reproducir a continuación">${ms('playlist_play')}</span><span class="iconbtn sl" title="Añadir a la cola">${ms('queue_music')}</span><span class="iconbtn sl" title="Añadir a playlist">${ms('playlist_add')}</span>
    <span class="iconbtn sl" title="Guardar en Tus me gusta">${ms('favorite')}</span><span class="iconbtn sl" title="Más">${ms('more_vert')}</span></div>`;

  /* Estados vacíos */
  S.empty = (kind) => {
    const e = {
      library: ['library_music', 'cookie', 'Tu biblioteca está vacía', 'Importa tus archivos de audio o descarga una lista pública de Spotify.', [['filled', 'download', 'Añadir música'], ['tonal', 'upload_file', 'Importar archivos']], 'M-20'],
      search: ['search_off', 'clover', 'Sin resultados para «zzyx»', 'Prueba con otro nombre, sin acentos, o busca por artista o playlist.', [['outlined', 'explore', 'Explorar']], 'M-15'],
      gone: ['playlist_remove', 'sunny', 'Esta lista ya no existe', 'Se eliminó o cambió de nombre. Tus canciones siguen en la biblioteca.', [['filled', 'home', 'Volver a Inicio']], 'M-14'],
      favs: ['favorite', 'flower', 'Aún no hay canciones guardadas', 'Toca el corazón de cualquier canción para tenerla aquí.', [['tonal', 'shuffle', 'Mezcla']], 'M-39'],
      queue: ['queue_music', 'softburst', 'La cola está vacía', 'Añade canciones con «Reproducir a continuación» o «Añadir a la cola».', [['tonal', 'library_music', 'Ir a la biblioteca']], 'M-51'],
    }[kind];
    return `<div class="empty" data-m="${e[5]}"><div class="glyph-wrap" style="--shape:${MX.shapes[e[1]]}">${ms(e[0], 1, 's48')}</div><h4>${e[2]}</h4><p>${e[3]}</p><div class="row gap-s">${e[4].map((b) => `<span class="btn ${b[0]}">${ms(b[1])}${b[2]}</span>`).join('')}</div></div>`;
  };

  /* ---------------- Búsqueda ---------------- */
  S.search = (mode = 'results') => {
    if (mode === 'browse') return `<div class="shelf-h" style="margin-top:6px" data-m="M-16"><h3>Explorar</h3><span>Colecciones de tu biblioteca</span></div><div class="browse">${[['Mar de fondo', 1], ['Tus me gusta', 4], ['Selección 1', 7], ['Recientes', 11], ['Para correr', 14], ['Cenas con ruido', 17], ['Domingo lento', 21], ['Cometas', 24]].map((b, i) => `<div class="bw" style="background:${MX.art(b[1])}">${b[0]}${MX.cover(b[1] + 3, { r: 'l' })}</div>`).join('')}</div>`;
    return `<div class="search-grid"><div data-m="M-17"><div class="shelf-h" style="margin-top:6px"><h3>Resultado principal</h3></div>
      <div class="top-result">${MX.cover(AR[0].seed, { shape: 'cookie', glyph: 'LA', gs: 'font-size:40px' })}<div><span class="chip" style="height:24px;padding:0 10px">Artista</span><b style="margin-top:8px">Lucía Aranda</b><span class="muted">42 canciones · 4 álbumes</span></div><span class="play">${ms('play_arrow', 1, 's32')}</span></div></div>
      <div><div class="shelf-h" style="margin-top:6px"><h3>Canciones</h3><a>Ver todas</a></div>${S.trows(T.slice(0, 4), { album: false, covers: true, cur: -1, hearts: [1] })}</div></div>
      ${shelf('Artistas', '', [AR[0], AR[3], AR[7]].map((a) => art(a)).join(''), '')}${shelf('Playlists y álbumes', '', [A[0], A[5]].map((a) => alb(a)).join('') + `<div class="poster">${mosaic(70)}<b>Mi playlist n.º 1</b><span>31 canciones</span></div>`, '')}`;
  };
  S.shortcuts = () => {
    const k = (...a) => a.map((x) => `<span class="kbd">${x}</span>`).join('');
    const rows = [['Reproducir / pausar', k('Espacio')], ['Anterior / siguiente', k('Ctrl', '←') + ' ' + k('→')], ['Volumen ±5', k('Ctrl', '↑') + ' ' + k('↓')], ['Silenciar', k('M')], ['Aleatorio', k('Ctrl', 'S')], ['Repetir', k('Ctrl', 'R')],
      ['Tus me gusta (actual)', k('Ctrl', '⇧', 'F')], ['Buscar', k('Ctrl', 'F') + ' ' + k('Ctrl', 'K')], ['Atrás / adelante', k('Alt', '←') + ' ' + k('→')], ['Ahora suena', k('Ctrl', 'P')], ['Letra', k('Ctrl', 'L')], ['Cola', k('Ctrl', 'Q')],
      ['Nueva playlist', k('Ctrl', 'N')], ['Importar archivos', k('Ctrl', 'O')], ['En la lista: reproducir', k('Enter')], ['En la lista: me gusta', k('F')], ['En la lista: ir al artista', k('Ctrl', 'Enter')], ['Atajos', k('F1')],
      ['Secciones 1–5 ' + NEW(), k('Alt', '1…5')], ['Enfocar contenido ' + NEW(), k('Ctrl', 'J')]];
    return `<div class="overlay"><div class="dialog wide" data-m="M-22"><h4>Atajos de teclado</h4><div class="keys">${rows.map((r) => `<div><span>${r[0]}</span><span>${r[1]}</span></div>`).join('')}</div>
      <p style="margin:14px 0 0">«nueva» = el README los describe pero el código actual no los implementa (discrepancias D1, D3, D4).</p><div class="acts" style="margin-top:12px"><span class="btn text">Cerrar</span></div></div></div>`;
  };

  /* ---------------- Añadir música ---------------- */
  S.downloads = () => `<div class="libhead"><h2>Añadir música</h2></div>
    <div class="dl-field" data-m="M-62"><div class="search focus" style="background:var(--m3-sc-highest)">${ms('link')}<span class="typed">https://open.spotify.com/playlist/37i9dQ…</span>${ms('close')}</div><span class="btn filled lg">Buscar</span></div>
    <div class="detect" data-m="M-63">${ms('library_music', 1)}<div><b>Playlist pública de Spotify · «Selección 1»</b><br><span style="opacity:.8">80 canciones publicadas (la vista pública puede limitar la lista). Se reutilizan las que ya tienes.</span></div></div>
    <div data-m="M-62">${[['Marea baja', 'Lucía Aranda', 'Ya en tu biblioteca'], ['Neón (en vivo)', 'Los Cuarzo', 'Versión distinta · revisar'], ['Cartas sin enviar', 'Mateo Brisa', ''], ['Hilo rojo', 'Iris Montoya', '']].map((r, i) => `<div class="srow"><span class="chk ${i > 1 ? 'on' : ''}">${i > 1 ? ms('check', 0, 's18') : ''}</span>${MX.cover(9 + i, { r: 's' })}<div><b class="ell">${r[0]}</b><span class="a">${r[1]}</span></div>${r[2] ? `<span class="status ${i === 1 ? 'rev' : ''}">${r[2]}</span>` : ''}</div>`).join('')}
      <div class="row gap-s" style="margin-top:8px"><span class="btn filled">${ms('download')}Descargar selección</span><span class="muted t-body-s">2 seleccionadas · ${NEW('Ctrl Enter')}</span></div></div>
    <div class="sect">Desde este equipo</div>
    <div class="device" data-m="M-64"><div class="dv sl"><div class="shape" style="--shape:${MX.shapes.cookie}">${ms('upload_file', 1)}</div><b>Importar archivos</b><span class="h">Ctrl O · abre el selector Wysun</span></div>
      <div class="dv sl"><div class="shape" style="--shape:${MX.shapes.clover}">${ms('create_new_folder', 1)}</div><b>Importar carpeta</b><span class="h">Lee las etiquetas incrustadas</span></div>
      <div class="dv sl"><div class="shape" style="--shape:${MX.shapes.flower}">${ms('folder_open', 1)}</div><b>Abrir carpeta de música</b><span class="h">~/Music/Wysun</span></div></div>
    <div class="dropzone hot" data-m="M-64">${ms('file_download', 0, 's32')}<div>Suelta archivos o carpetas de audio aquí ${NEW()}</div></div>
    <div class="sect">Descargas <span class="muted t-body-s" style="margin-left:auto;font-weight:400">${ms('info', 0, 's18')} 3 de 5</span></div>
    <div class="row gap-s" data-m="M-65" style="margin-bottom:8px"><span class="btn tonal">${ms('play_arrow', 1)}Continuar</span><span class="btn outlined">${ms('pause')}Pausar cola</span><span class="btn text">${ms('refresh')}Reintentar errores</span></div>
    <div data-m="M-65">${[['Cartas sin enviar', 'run', 'Descargando · 64 %', 64], ['Hilo rojo', 'wait', 'En cola', 0], ['Neón (en vivo)', 'rev', 'Revisar versión', 0], ['Sal y sol', 'err', 'Error · sin resultados con esa duración', 0], ['Cometas', 'wait', 'En cola', 0]].map((r, i) => `<div class="srow" style="grid-template-columns:48px minmax(0,1fr) auto">${MX.cover(14 + i, { r: 's' })}<div><b class="ell">${r[0]}</b><span class="a">Esperando turno</span>${r[3] ? `<div class="lin"><i style="width:${r[3]}%"></i></div>` : r[1] === 'run' ? '<div class="lin ind"><i></i></div>' : ''}</div><span class="status ${r[1] === 'wait' ? '' : r[1]}">${r[2]}</span></div>`).join('')}</div>`;

  /* ---------------- Ahora suena ---------------- */
  const LYR = ['Dejé la sal en la ventana', 'y el mapa sin doblar', 'Si el mar se lleva la hora', 'yo me quedo a escuchar', 'Marea baja, marea baja', 'enséñame a no volver', 'Y si la luz se hace lenta', 'también sé esperar'];
  S.lyrics = (state = 'synced') => {
    if (state === 'loading') return `<div class="lyr"><div class="skel" style="width:60%"></div><div class="skel" style="width:82%"></div><div class="skel" style="width:48%"></div><div class="skel" style="width:70%"></div><p style="opacity:.6;font-size:16px;font-weight:500">Buscando letra…</p></div>`;
    if (state === 'instr') return `<div class="empty" style="height:100%">${'' }<div class="glyph-wrap" style="--shape:${MX.shapes.flower}">${ms('piano', 1, 's48')}</div><h4>Instrumental</h4><p>No hay letra para esta canción.</p></div>`;
    if (state === 'missing') return `<div class="empty" style="height:100%"><div class="glyph-wrap" style="--shape:${MX.shapes.clover}">${ms('lyrics', 0, 's48')}</div><h4>La letra no está disponible para esta versión</h4><p>Solo se muestran letras que coinciden en título, artista y duración (±2 s).</p></div>`;
    const cur = 4, synced = state === 'synced';
    return `<div class="lyr" data-m="M-52">${LYR.map((l, i) => `<p class="${synced ? (i === cur ? 'cur' : Math.abs(i - cur) === 1 ? 'd1' : Math.abs(i - cur) > 2 ? 'far' : '') : 'd1'}">${l}${synced ? `<small>${ms('arrow_right_alt', 0, 's18')} 1:2${i}</small>` : ''}</p>`).join('')}</div>`;
  };
  S.lyricFoot = (state = 'synced') => `<div class="lyr-foot" data-m="M-53"><span>${state === 'synced' ? 'Sincronizada' : 'Sin sincronizar'} · LRCLIB</span><span style="margin-left:auto">Desfase</span>
    <span class="iconbtn sl tonal" title="Adelantar la letra 0.5 s">${ms('remove')}</span><b style="min-width:46px;text-align:center;font-weight:500">+0.5 s</b><span class="iconbtn sl tonal" title="Retrasar la letra 0.5 s">${ms('add')}</span></div>`;
  S.queue = (empty) => empty ? S.empty('queue') : `<div class="qlist" data-m="M-51"><div class="qh">Sonando ahora</div>
      <div class="qrow cur"><span class="eqbars">${'<i></i>'.repeat(3)}</span>${MX.cover(1, { r: 's' })}<div><b class="ell">Marea baja</b><span class="a ell">Lucía Aranda</span></div><span class="d">3:42</span><span></span></div>
      <div class="qh">A continuación <span>De Mar de fondo</span><span style="margin-left:auto">${NEW('arrastrar')}</span></div>
      ${T.slice(1, 7).map((t, i) => `<div class="qrow"><span class="grip">${ms('drag_indicator', 0, 's18')}</span>${MX.cover(1 + i, { r: 's' })}<div><b class="ell">${t.t}</b><span class="a ell">${t.a.split(',')[0]}</span></div><span class="d">${t.d}</span><span class="iconbtn sl" style="width:32px;height:32px">${ms('more_vert', 0, 's20')}</span></div>`).join('')}</div>`;
  S.queueMenu = (style) => `<div class="menu floating" style="${style}" data-m="M-51">${mi('play_arrow', 'Reproducir ahora')}${mi('remove_circle', 'Quitar de la cola')}${mi('more_horiz', 'Más opciones…')}</div>`;

  // Reproductor completo; o: tab ('lyrics'|'queue'), playing, width, lyricState, queueEmpty, menu
  S.nowPlaying = (o = {}) => {
    const playing = o.playing !== false, tab = o.tab || 'lyrics';
    const body = `<div class="np" data-m="M-49"><div class="halo" style="background:${MX.art(1)}"></div>
      <div class="topline"><span class="iconbtn tonal sl" title="Cerrar · Esc">${ms('expand_more')}</span><span class="t">Ahora suena${o.ctx === false ? '' : ' · Mar de fondo'}</span><span class="iconbtn sl" title="Más opciones">${ms('more_vert')}</span></div>
      <div class="left"><div class="bigcover"><div style="width:100%;display:contents">${MX.cover(1, { shape: playing ? 'cookie' : 'circle', attrs: 'data-act="cover"' })}</div></div>
        <div class="meta"><div class="row gap-m"><div class="grow"><h3 class="ell">Marea baja</h3><div class="ar" data-m="M-49">Lucía Aranda</div><div class="al ell">Mar de fondo</div></div>
          <span class="iconbtn tonal sl on heart-btn" data-act="heart" data-m="M-39" style="width:44px;height:44px;color:var(--m3-tertiary)">${ms('favorite', 1)}</span></div>
          <div class="progress" style="margin-top:14px" data-m="M-46"><span class="time">1:24</span><div class="wave" style="height:18px">${MX.wave(.38, playing)}</div><span class="time">3:42</span></div><div class="q"><span></span><span>opus · 160 kb/s</span><span></span></div></div>
        <div class="ctl"><span class="iconbtn sl" data-m="M-48">${ms('shuffle')}</span><span class="iconbtn tonal sl">${ms('skip_previous', 1, 's32')}</span><button class="playbtn lg ${playing ? 'playing' : ''}" data-act="play">${ms(playing ? 'pause' : 'play_arrow', 1, 's48')}</button>
          <span class="iconbtn tonal sl">${ms('skip_next', 1, 's32')}</span><span class="iconbtn sl on" style="background:transparent;color:var(--m3-primary)" title="Repetir lista">${ms('repeat')}</span></div>
        <div class="row gap-s" style="width:min(100%,420px);justify-content:center" data-m="M-47"><span class="iconbtn sl">${ms('volume_down')}</span><div class="vol" style="width:180px"><i></i><b></b></div><span class="iconbtn sl">${ms('volume_up')}</span></div></div>
      <div class="right"><div data-tabs="np"><div class="tabs" data-m="M-50"><div class="tab ${tab === 'lyrics' ? 'on' : ''}" data-tab="lyrics">${ms('lyrics', 0, 's20')}Letra</div><div class="tab ${tab === 'queue' ? 'on' : ''}" data-tab="queue">${ms('queue_music', 0, 's20')}A continuación</div></div></div>
        <div class="panel" style="${tab === 'queue' ? 'mask-image:none;overflow:auto' : ''}">${tab === 'lyrics' ? S.lyrics(o.lyricState || 'synced') : S.queue(o.queueEmpty)}</div>${tab === 'lyrics' && !['loading', 'instr', 'missing'].includes(o.lyricState) ? S.lyricFoot(o.lyricState || 'synced') : ''}</div></div>`;
    return `<div class="m3 ${o.fixed ? 'fixed' : ''}" data-palette="${o.palette || 'grafito'}" data-mode="${o.mode || 'dark'}"><div class="win npwin ${o.cls || ''}" style="width:${o.width || 1040}px" id="${o.id || ''}">${body}${o.floating || ''}</div></div>`;
  };

  /* Cápsula suelta, para mostrar sus estados */
  S.capsule = (width, p) => `<div class="m3" data-palette="grafito" data-mode="dark"><div class="win short" style="width:${width}px;height:120px"><div class="main" style="position:relative"><div class="content" style="opacity:.0"></div>${MX.player(p)}</div></div></div>`;
})();
