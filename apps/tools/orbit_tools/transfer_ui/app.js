(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const search = $('#search'), rows = [...document.querySelectorAll('.file-row')];
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    let shown = 0;
    rows.forEach(row => { row.hidden = !row.dataset.name.toLocaleLowerCase().includes(query); if (!row.hidden) shown++; });
    $('#count').textContent = shown;
    $('#no-results').hidden = !query || shown > 0;
    $('#empty').hidden = rows.length > 0 || !!query;
  });

  const section = $('#upload-section');
  if (section.hidden) return;
  const input = $('#files'), drop = $('#dropzone'), queue = $('#queue'), template = $('#queue-template');
  const controls = $('#transfer-controls'), send = $('#send'), clear = $('#clear'), cancel = $('#cancel'), message = $('#message');
  const maxBytes = Number(section.dataset.maxBytes);
  let items = [], busy = false, cancelled = false, active = null, dragDepth = 0;
  const sizes = bytes => {
    let value = bytes, unit = 0; const units = ['B', 'KB', 'MB', 'GB'];
    while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
    return `${unit ? value.toFixed(1) : value} ${units[unit]}`;
  };
  const available = () => items.filter(item => item.state !== 'done' && item.file.size <= maxBytes);
  const update = () => {
    const pending = available().length;
    controls.hidden = !items.length;
    send.hidden = busy;
    send.disabled = !pending;
    send.textContent = pending > 1 ? `Enviar ${pending}` : 'Enviar';
    clear.hidden = busy;
    cancel.hidden = !busy;
    drop.disabled = busy;
    items.forEach(item => { item.row.querySelector('.remove').disabled = busy; });
  };
  const paint = item => {
    item.row.dataset.state = item.state;
    item.row.querySelector('.queue-state').textContent = item.label;
    item.row.querySelector('.queue-percent').textContent = item.state === 'sending' ? `${item.percent}%` : '';
    const progress = item.row.querySelector('progress');
    progress.value = item.percent;
    progress.setAttribute('aria-label', `Progreso de ${item.file.name}`);
  };
  const removeItem = item => {
    if (busy) return;
    const position = items.indexOf(item);
    const restoreFocus = item.row.contains(document.activeElement);
    items = items.filter(value => value !== item);
    item.row.classList.add('leaving');
    item.row.setAttribute('aria-hidden', 'true');
    item.row.inert = true;
    setTimeout(() => item.row.remove(), window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 150);
    message.textContent = '';
    update();
    if (restoreFocus) (items[position]?.row.querySelector('.remove') || items[position - 1]?.row.querySelector('.remove') || drop).focus();
  };
  const addFiles = files => {
    if (busy) return;
    let limitHit = false;
    for (const file of files) {
      if (items.length >= 50) { limitHit = true; break; }
      if (items.some(item => item.state !== 'done' && item.file.name === file.name && item.file.size === file.size && item.file.lastModified === file.lastModified)) continue;
      const item = { file, state: file.size > maxBytes ? 'error' : 'queued', label: file.size > maxBytes ? 'Supera el límite' : 'Listo', percent: 0, row: template.content.firstElementChild.cloneNode(true) };
      item.row.querySelector('.queue-name').textContent = file.name;
      item.row.querySelector('.queue-name').title = file.name;
      item.row.querySelector('.queue-size').textContent = sizes(file.size);
      item.row.querySelector('.remove').setAttribute('aria-label', `Quitar ${file.name}`);
      item.row.querySelector('.remove').addEventListener('click', () => removeItem(item));
      items.push(item); queue.append(item.row); paint(item);
    }
    message.textContent = limitHit ? 'Máximo 50 archivos.' : '';
    update();
  };
  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', () => { addFiles(input.files); input.value = ''; });
  document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); });
  document.addEventListener('drop', event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); });
  drop.addEventListener('dragenter', event => { event.preventDefault(); if (!busy) { dragDepth++; drop.classList.add('dragging'); } });
  drop.addEventListener('dragover', event => { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = busy ? 'none' : 'copy'; });
  drop.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; drop.classList.remove('dragging'); } });
  drop.addEventListener('drop', event => { event.preventDefault(); dragDepth = 0; drop.classList.remove('dragging'); addFiles(event.dataTransfer.files); });
  clear.addEventListener('click', () => {
    if (busy) return;
    items = []; queue.replaceChildren(); message.textContent = ''; update(); drop.focus();
  });
  cancel.addEventListener('click', () => { cancelled = true; cancel.disabled = true; active?.abort(); });
  const upload = item => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest(); active = xhr;
    xhr.open('PUT', '/api/upload');
    xhr.timeout = 120000;
    xhr.setRequestHeader('X-Filename', encodeURIComponent(item.file.name));
    xhr.upload.onprogress = event => {
      if (!event.lengthComputable) return;
      item.percent = Math.round(event.loaded / event.total * 100);
      item.label = item.percent === 100 ? 'Guardando…' : 'Enviando'; paint(item);
    };
    xhr.onload = () => {
      if (xhr.status === 201) resolve();
      else reject(new Error(({ 401: 'Acceso requerido', 403: 'Acceso denegado', 413: 'Supera el límite', 429: 'Intenta de nuevo', 503: 'Servidor ocupado' })[xhr.status] || 'Error de envío'));
    };
    xhr.onerror = () => reject(new Error('Sin conexión'));
    xhr.ontimeout = () => reject(new Error('Tiempo agotado'));
    xhr.onabort = () => reject(new Error('Cancelado'));
    xhr.send(item.file);
  });
  send.addEventListener('click', async () => {
    if (busy || !available().length) return;
    busy = true; cancelled = false; cancel.disabled = false; update();
    let completed = 0, failed = 0;
    try {
      for (const item of available()) {
        if (cancelled) break;
        item.state = 'sending'; item.label = 'Enviando'; item.percent = 0; paint(item);
        message.textContent = `Enviando ${completed + failed + 1} de ${available().length + completed}`;
        try {
          await upload(item);
          item.state = 'done'; item.label = 'Recibido'; item.percent = 100; completed++;
        } catch (error) {
          item.state = 'error'; item.label = error.message; failed++;
        } finally { active = null; paint(item); }
        if (cancelled) break;
      }
    } finally {
      busy = false; update();
      message.textContent = cancelled ? 'Envío cancelado.' : failed ? `${completed} enviados · ${failed} pendientes` : completed === 1 ? 'Archivo enviado.' : `${completed} archivos enviados.`;
      (send.disabled ? clear : send).focus();
    }
  });
  window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });
  update();
})();
