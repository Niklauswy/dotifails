/* Wysun Files · maquetas — ventana, navegación adaptable, barra de ruta y piezas comunes.
   Reutiliza los tokens y componentes de music-shared.css/js (paletas, modo, chips, menús, diálogos). Cada elemento
   con data-m="F-xx" corresponde a una fila de docs/superpowers/specs/2026-10-26-qml-paridad-music-files.md. */
(function () {
  const MX = window.MX, ms = MX.ms, FX = (window.FX = {});
  FX.ms = ms;

  /* Tipos: icono, forma del emblema y rol de color (categorías de Files). */
  FX.kinds = {
    folder: ['folder', 'squircle', 'secondary'], image: ['image', 'flower', 'tertiary'], video: ['movie', 'pill', 'tertiary'],
    audio: ['music_note', 'cookie', 'primary'], doc: ['description', 'squircle', 'primary'], pdf: ['picture_as_pdf', 'squircle', 'error'],
    code: ['code', 'gem', 'secondary'], archive: ['folder_zip', 'clover', 'secondary'], md: ['article', 'squircle', 'primary'],
  };
  FX.files = [
    ['clases', 'folder', '12 elementos', 'ayer'], ['Latex', 'folder', '34 elementos', 'hace 3 días'], ['Music', 'folder', '210 elementos', '20 oct'],
    ['proyectos', 'folder', '8 elementos', 'hoy'], ['repos', 'folder', '17 elementos', 'hoy'], ['Downloads', 'folder', '96 elementos', 'hoy'],
    ['tesis.pdf', 'pdf', '2,4 MB', 'hoy'], ['notas.md', 'md', '6 KB', 'hoy'], ['playa.jpg', 'image', '3,1 MB', '18 oct'],
    ['montaña.png', 'image', '5,8 MB', '12 oct'], ['clip.mp4', 'video', '84 MB', '2 oct'], ['ensayo.ogg', 'audio', '4,2 MB', '30 sep'],
    ['main.py', 'code', '12 KB', 'ayer'], ['respaldo.zip', 'archive', '1,2 GB', 'sep'],
  ];

  const tone = (role) => `background:var(--m3-${role}-container);color:var(--m3-on-${role}-container)`;
  FX.thumb = (kind, o = {}) => {
    const k = FX.kinds[kind];
    if (kind === 'image' && !o.icon) return MX.cover(o.seed || 3, { r: 'm', cls: 'fthumb' });
    return `<div class="fthumb kind" style="${tone(k[2])};--shape:${MX.shapes[k[1]] || MX.shapes.squircle}">${ms(k[0], 1)}</div>`;
  };
  FX.tile = (f, o = {}) => `<div class="ftile ${o.sel ? 'sel' : ''} ${o.cut ? 'cut' : ''}" ${o.m ? `data-m="${o.m}"` : ''}>${o.sel ? `<span class="sel-check">${ms('check', 0, 's18')}</span>` : ''}${FX.thumb(f[1], { seed: o.seed })}<b class="ell">${f[0]}</b><span class="ell">${f[2]}</span></div>`;
  FX.row = (f, o = {}) => `<div class="frow ${o.sel ? 'sel' : ''}">${FX.thumb(f[1], { seed: o.seed, icon: true })}<b class="ell">${f[0]}</b><span class="ell m">${f[3]}</span><span class="m">${f[1] === 'folder' ? '—' : f[2]}</span><span class="m type">${{ folder: 'Carpeta', image: 'Imagen', video: 'Vídeo', audio: 'Audio', doc: 'Documento', pdf: 'PDF', code: 'Código', archive: 'Archivo', md: 'Markdown' }[f[1]]}</span></div>`;

  /* Navegación: los mismos destinos en drawer, rail y modal. */
  const FAV = [['home', 'home', 'Inicio'], ['desk', 'desktop_windows', 'Escritorio'], ['docs', 'description', 'Documentos'], ['dl', 'download', 'Descargas'], ['img', 'image', 'Imágenes'], ['mus', 'music_note', 'Música'], ['vid', 'movie', 'Vídeos']];
  const RAIL = [['home', 'home', 'Inicio'], ['dl', 'download', 'Descargas'], ['docs', 'description', 'Docs'], ['img', 'image', 'Imágenes'], ['trash', 'delete', 'Papelera']];
  function navItems(route) {
    const mk = (r, i, l, extra = '', m = '') => `<div class="item sl ${route === r ? 'on' : ''}" ${m ? `data-m="${m}"` : ''}>${ms(i, route === r)}<span class="grow ell">${l}</span>${extra}</div>`;
    const usage = (free, pct) => `<span class="usage"><i style="width:${pct}%"></i></span><span class="free">${free}</span>`;
    return `<div class="head" data-m="F-10">Favoritos</div>` + FAV.map((n) => mk(...n)).join('') +
      `<div class="head" data-m="F-11">Marcadores</div>` + mk('bm1', 'bookmark', 'wysun-shell') + mk('bm2', 'bookmark', 'Tesis 2026') +
      `<div class="head">Dispositivos</div>` + mk('sys', 'hard_drive', 'Sistema', usage('25 GB libres', 78), 'F-10') + mk('usb', 'usb', 'KINGSTON', usage('11 GB libres', 31) + ms('eject')) +
      `<div class="divider"></div>` + mk('trash', 'delete', 'Papelera');
  }
  function nav(route) {
    const rail = `<nav class="rail"><div class="menu-btn-r">${ms('menu')}</div><div class="fab" title="Nuevo">${ms('add')}</div>` +
      RAIL.map((n) => `<div class="item ${route === n[0] ? 'on' : ''}"><div class="ind sl">${ms(n[1], route === n[0])}</div>${n[2]}</div>`).join('') + `</nav>`;
    const fab = `<div class="fab" data-m="F-32">${ms('add')}Nuevo</div>`;
    return rail + `<nav class="drawer">${fab}${navItems(route)}</nav><div class="scrim" data-act="close-nav"></div><nav class="modal">${fab}${navItems(route)}</nav>`;
  }

  /* Barra superior: atrás/adelante/subir, ruta segmentada (Ctrl+L la edita), filtro, vista, más. */
  FX.topbar = (o = {}) => {
    const crumbs = (o.path || ['Inicio', 'Documentos', 'clases']).map((c, i, a) => `<span class="crumb ${i === a.length - 1 ? 'last' : ''}">${i === 0 ? ms('home', 0, 's18') : ''}${c}</span>`).join(ms('chevron_right', 0, 's18 sep'));
    return `<header class="topbar ftop">
      <span class="iconbtn sl menu-btn" data-act="open-nav">${ms('menu')}</span>
      <span class="iconbtn sl" data-m="F-14" title="Atrás · Alt+←">${ms('arrow_back')}</span>
      <span class="iconbtn sl hide-compact" title="Adelante · Alt+→">${ms('arrow_forward')}</span>
      <span class="iconbtn sl hide-compact" title="Carpeta superior · Alt+↑">${ms('arrow_upward')}</span>
      ${o.editPath ? `<div class="path editing" data-m="F-12">${ms('edit', 0, 's18')}<span class="typed">/home/nicolas/Documentos/clases</span></div>` : `<div class="path" data-m="F-12">${crumbs}</div>`}
      <div class="seg hide-compact" data-m="F-20"><span class="${o.list ? '' : 'on'}">${ms(o.list ? 'grid_view' : 'check', 0, 's18')}</span><span class="${o.list ? 'on' : ''}">${ms(o.list ? 'check' : 'view_list', 0, 's18')}</span></div>
      <span class="iconbtn sl hide-compact" data-m="F-50" title="Vista previa · Ctrl+I">${ms('right_panel_open')}</span>
      <span class="iconbtn sl" data-m="F-32" title="Más acciones">${ms('more_vert')}</span>
    </header>`;
  };
  FX.tabs = (n = 2) => `<div class="ftabs" data-m="F-13">${['clases', 'Descargas', 'Latex'].slice(0, n).map((t, i) => `<span class="ftab ${i === 0 ? 'on' : ''}">${ms('folder', i === 0, 's18')}${t}${ms('close', 0, 's18')}</span>`).join('')}<span class="iconbtn sl" title="Nueva pestaña · Ctrl+T">${ms('add')}</span></div>`;

  /* Cabecera de la carpeta: el emblema expresivo junto al título y el resumen. */
  FX.hero = (o = {}) => `<div class="fhero" data-m="F-26"><div class="emblem" style="--shape:${MX.shapes[o.shape || 'cookie']};${tone(o.role || 'primary')}">${ms(o.icon || 'school', 1)}</div>
    <div><h2>${o.title || 'clases'}</h2><p>${o.summary || '6 carpetas · 8 archivos · 1,3 GB'}</p></div></div>`;
  FX.filterField = (text) => `<div class="search fsearch ${text ? 'focus' : ''}" data-m="F-24">${ms('filter_list')}${text ? `<span class="typed">${text}</span>${ms('close')}` : `<span>Filtrar</span><kbd>Ctrl F</kbd>`}</div>`;
  FX.filters = (on = 'all', text = '') => `<div class="frow-filters">${FX.filterField(text)}<div class="chips fchips" data-m="F-24">${[['all', 'Todo'], ['dir', 'Carpetas'], ['img', 'Imágenes'], ['vid', 'Vídeos'], ['aud', 'Audio'], ['doc', 'Documentos'], ['code', 'Código']].map(([k, t]) => `<span class="chip ${on === k ? 'on' : ''}" data-toggle>${on === k ? ms('check') : ''}${t}</span>`).join('')}</div></div>`;
  FX.status = (o = {}) => `<footer class="fstatus" data-m="F-27"><span>${o.text || '14 elementos'}</span>${o.sel ? `<span>· ${o.sel} seleccionados</span>` : ''}<span class="grow"></span>${o.op ? `<span class="op">${ms('content_copy', 0, 's18')}${o.op}<span class="bar"><i style="width:${o.pct || 40}%"></i></span></span>` : ''}<span>25 GB libres</span></footer>`;

  FX.win = function (o) {
    return `<div class="m3 ${o.fixed ? 'fixed' : ''}" data-palette="${o.palette || 'grafito'}" data-mode="${o.mode || 'dark'}">
      <div class="win fwin ${o.cls || ''} ${o.navOpen ? 'nav-open' : ''}" style="${o.width ? `width:${o.width}px` : 'width:100%'}">
        ${nav(o.route || 'docs')}
        <div class="main">${o.tabs ? FX.tabs(o.tabs) : ''}${FX.topbar(o.top || {})}
          <div class="fbody"><div class="content">${o.content}</div>${o.inspector ? `<aside class="inspector" data-m="F-50">${o.inspector}</aside>` : ''}</div>
          ${FX.status(o.status || {})}${o.snack ? `<div class="snack">${o.snack}</div>` : ''}${o.floating || ''}</div>
        ${o.overlay || ''}
      </div></div>`;
  };

  FX.selbar = (n) => `<div class="selbar" data-m="F-29"><span class="iconbtn sl" title="Quitar selección · Esc">${ms('close')}</span><b>${n} seleccionados</b>
    <span class="iconbtn sl" title="Abrir">${ms('open_in_new')}</span><span class="iconbtn sl" title="Copiar · Ctrl+C">${ms('content_copy')}</span><span class="iconbtn sl" title="Cortar · Ctrl+X">${ms('content_cut')}</span>
    <span class="iconbtn sl" title="Cambiar nombre · F2">${ms('drive_file_rename_outline')}</span><span class="iconbtn sl" title="Papelera · Supr">${ms('delete')}</span><span class="iconbtn sl" title="Más">${ms('more_vert')}</span></div>`;
  const mi = (icon, label, key = '', cls = '') => `<div class="mi ${cls}">${icon ? ms(icon) : '<span style="width:24px"></span>'}${label}${key ? `<span class="key">${key}</span>` : ''}</div>`;
  FX.mi = mi;
  FX.contextMenu = (style = 'left:330px;top:210px') => `<div class="menu floating" style="${style}" data-m="F-31">
    ${mi('open_in_new', 'Abrir', 'Enter')}${mi('tab', 'Abrir en nueva pestaña')}${mi('preview', 'Vista previa ampliada', 'Espacio')}<hr>
    ${mi('content_copy', 'Copiar', 'Ctrl C')}${mi('content_cut', 'Cortar', 'Ctrl X')}${mi('content_paste', 'Pegar aquí', 'Ctrl V')}<hr>
    ${mi('drive_file_rename_outline', 'Cambiar nombre…', 'F2')}${mi('link', 'Copiar ruta')}${mi('terminal', 'Terminal aquí')}${mi('info', 'Propiedades', 'Alt Enter')}<hr>
    ${mi('delete', 'Enviar a la papelera', 'Supr', 'danger')}</div>`;
  FX.newMenu = (style) => `<div class="menu floating" style="${style}" data-m="F-32">${mi('create_new_folder', 'Carpeta', 'Ctrl ⇧ N')}${mi('note_add', 'Archivo vacío')}</div>`;
  FX.moreMenu = (style) => `<div class="menu floating" style="${style}" data-m="F-32">${mi('tab', 'Nueva pestaña', 'Ctrl T')}${mi('arrow_upward', 'Carpeta superior', 'Alt ↑')}${mi('bookmark_add', 'Añadir a marcadores')}<hr>
    ${mi('terminal', 'Terminal aquí')}${mi('visibility', 'Mostrar archivos ocultos', 'Ctrl H')}${mi('sort', 'Ordenar por nombre', '▸')}${mi('link', 'Copiar ruta')}${mi('info', 'Propiedades')}</div>`;
})();
