"""Standalone transfer UI with escaped directory data and no external assets."""
from pathlib import Path
import html
import urllib.parse

ASSETS=Path(__file__).with_name('transfer_ui')
ICONS={
 'file':'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
 'folder':'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
 'download':'<path d="M12 3v12m-5-5 5 5 5-5M5 17v3h14v-3"/>',
 'upload':'<path d="M12 16V4m-5 5 5-5 5 5M4 17v4h16v-4"/>',
 'arrow':'<path d="m9 5 7 7-7 7"/>',
 'back':'<path d="m14 5-7 7 7 7"/>',
 'check':'<path d="m5 12 4 4L19 6"/>',
 'x':'<path d="m6 6 12 12M6 18 18 6"/>',
 'search':'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
 'image':'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1"/><path d="m21 15-5-5L3 21"/>',
 'code':'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-16-2 20"/>',
}

def icon(name):
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+ICONS[name]+'</svg>'


def size_label(value):
    for unit in ('B','KB','MB','GB','TB'):
        if value<1024 or unit=='TB':return f'{value:.0f} {unit}' if unit=='B' else f'{value:.1f} {unit}'
        value/=1024


def render(folder,root,entries,*,uploads,max_bytes,nonce,authenticated=False):
    rows=[]
    for i,(name,is_dir,size) in enumerate(entries):
        suffix='/' if is_dir else ''
        extension=Path(name).suffix.lower()
        kind='folder' if is_dir else 'image' if extension in {'.png','.jpg','.jpeg','.webp','.gif','.svg'} else 'code' if extension in {'.py','.js','.ts','.tsx','.html','.css','.json','.sh'} else 'file'
        label='Abrir carpeta' if is_dir else 'Descargar'
        rows.append('<a class="file-row" href="'+urllib.parse.quote(name,safe='')+suffix+'" data-name="'+html.escape(name,quote=True)+'" style="--delay:'+str(min(i,7)*28)+'ms"'+(' download' if not is_dir else '')+'>'+ '<span class="file-icon">'+icon(kind)+'</span><span class="file-name">'+html.escape(name)+'</span><span class="file-size">'+('Carpeta' if is_dir else size_label(size))+'</span><span class="file-action" aria-label="'+label+'">'+icon('arrow' if is_dir else 'download')+'</span></a>')
    breadcrumbs=['<a href="/">Archivos</a>']
    relative=folder.relative_to(root)
    for i,name in enumerate(relative.parts):
        href='/'+ '/'.join(urllib.parse.quote(p,safe='') for p in relative.parts[:i+1])+'/'
        breadcrumbs.extend(['<span aria-hidden="true">/</span>','<a href="'+href+'">'+html.escape(name)+'</a>'])
    if len(breadcrumbs)==1:breadcrumbs=['<span>Archivos</span>']
    html_page=(ASSETS/'page.html').read_text()
    replacement={
      'STYLE':(ASSETS/'style.css').read_text(),'SCRIPT':(ASSETS/'app.js').read_text(),
      'NONCE':nonce,'ROWS':''.join(rows),'COUNT':str(len(entries)),
      'BREADCRUMBS':''.join(breadcrumbs),'EMPTY_HIDDEN':' hidden' if entries else '',
      'UPLOAD_HIDDEN':'' if uploads else ' hidden','MAX_BYTES':str(max_bytes),
      'MAX_SIZE':size_label(max_bytes),'ACCESS':'Con código' if authenticated else 'Compartido',
      'PARENT':'<a class="back" href="../" aria-label="Volver a la carpeta anterior">'+icon('back')+'</a>' if folder!=root else '',
      'ICON_UPLOAD':icon('upload'),'ICON_SEARCH':icon('search'),'ICON_FILE':icon('file'),
      'ICON_X':icon('x'),'ICON_CHECK':icon('check'),
    }
    # One substitution pass: file names containing placeholder syntax stay literal.
    import re
    return re.sub(r'\{\{([A-Z_]+)\}\}',lambda match:replacement[match[1]],html_page).encode()
