"""Local PDF engine. Owned exclusively by the reader's worker process."""
import json
from pathlib import Path
import sys

import fitz

from wysun_core.jsonio import atomic_path
from pdf_layout import raster_width

OPERATIONS = {'open', 'render', 'thumbnail', 'page_info', 'search', 'annotations', 'annotate', 'update_note',
              'delete', 'save'}
CONTEXT = 120  # characters of a search result's line


def fingerprint(path):
    info = Path(path).stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


class PdfEngine:
    def __init__(self):
        self.doc = None
        self.path = None
        self.dirty = False
        self.editable = False

    def open(self, path, password=''):
        path = Path(path).expanduser().resolve(strict=True)
        candidate = fitz.open(path)
        try:
            if not candidate.is_pdf:
                raise ValueError('Selecciona un documento PDF.')
            owner = 0
            if candidate.needs_pass:
                owner = candidate.authenticate(password)
                if not owner:
                    return {'password_required': True}
            if not candidate.page_count:
                raise ValueError('El PDF no contiene páginas.')
            editable = bool(owner & 4 or candidate.permissions & fitz.PDF_PERM_ANNOTATE)
            # Rotated sizes of every page: the reader lays the whole document out without rendering it.
            sizes = [[page.rect.width, page.rect.height] for page in candidate]
            result = {'path': str(path), 'pages': candidate.page_count, 'sizes': sizes,
                      'outline': candidate.get_toc()[:10000], 'editable': editable}
            stamp = fingerprint(path)
            if self.doc:
                self.doc.close()
            self.doc, candidate = candidate, None
            self.path, self.stamp = path, stamp
            self.dirty, self.editable = False, editable
            return result
        finally:
            if candidate is not None:
                candidate.close()

    @staticmethod
    def _raster(page, scale):
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        # Raw RGB888 rows travel as a binary frame after the JSON header: no PNG encode or decode.
        return {'width': pix.width, 'height': pix.height, 'stride': pix.stride, '_blob': bytes(pix.samples)}

    def render(self, page, width):
        p = self.doc[page]
        pixels = raster_width(p.rect.width, p.rect.height, max(16, width))
        return {'page': page, **self._raster(p, pixels / p.rect.width)}

    def thumbnail(self, page):
        p = self.doc[page]
        return {'page': page, **self._raster(p, min(120 / p.rect.width, 170 / p.rect.height))}

    def page_info(self, page):
        p = self.doc[page]
        words = []
        for word in p.get_text('words', sort=True):
            rect = fitz.Rect(word[:4]) * p.rotation_matrix
            words.append([*rect, word[4], word[5], word[6]])
        links = []
        for link in p.get_links():
            rect = list(fitz.Rect(link['from']))  # MuPDF reports link areas already rotated
            if link.get('uri'):
                links.append({'rect': rect, 'uri': link['uri']})
            elif link.get('page', -1) >= 0 and link['page'] < self.doc.page_count:
                to = link.get('to')
                # The target point is reliable on upright pages; a rotated target opens at its top.
                y = fitz.Point(to).y if to is not None and not self.doc[link['page']].rotation else 0
                links.append({'rect': rect, 'page': link['page'], 'y': max(0.0, y)})
        annotations = [{'xref': a.xref, 'text': a.info.get('content') or '', 'type': a.type[1],
                        'rect': list(a.rect * p.rotation_matrix)} for a in p.annots() or ()]
        return {'page': page, 'words': words, 'links': links, 'annotations': annotations}

    def search(self, page, text):
        p = self.doc[page]
        hits = [fitz.Rect(r) for r in p.search_for(text)][:1000]
        lines = {}
        for word in p.get_text('words', sort=True):
            lines.setdefault((word[5], word[6]), []).append(word)
        contexts = []
        for hit in hits:
            line = next((words for words in lines.values()
                         if any(fitz.Rect(w[:4]).intersects(hit) for w in words)), [])
            contexts.append(_excerpt(' '.join(w[4] for w in line), text))
        return {'page': page, 'hits': [list(r * p.rotation_matrix) for r in hits], 'contexts': contexts}

    def annotations(self):
        items = []
        for p in self.doc:
            for a in p.annots() or ():
                items.append({'page': p.number, 'xref': a.xref, 'type': a.type[1],
                              'text': a.info.get('content') or ''})
        return {'items': items}

    def annotate(self, page, kind, rects=None, point=None, text='', colour=None):
        if not self.editable:
            raise ValueError('El documento no permite anotaciones.')
        p = self.doc[page]
        if kind == 'note':
            a = p.add_text_annot(fitz.Point(point) * p.derotation_matrix, text)
        elif kind in ('highlight', 'underline') and rects:
            quads = [fitz.Quad(fitz.Rect(r).quad) * p.derotation_matrix for r in rects]
            a = (p.add_highlight_annot if kind == 'highlight' else p.add_underline_annot)(quads)
            a.set_info(content=text)
        else:
            raise ValueError('Selecciona texto antes de anotar.')
        if colour:
            a.set_colors(stroke=colour)
        a.update()
        self.dirty = True
        return {'dirty': True}

    def update_note(self, page, xref, text):
        if not self.editable:
            raise ValueError('El documento no permite anotaciones.')
        p = self.doc[page]
        annotation = p.load_annot(xref)
        annotation.set_info(content=text)
        annotation.update()
        self.dirty = True
        return {'dirty': True}

    def delete(self, page, xref):
        if not self.editable:
            raise ValueError('El documento no permite anotaciones.')
        p = self.doc[page]
        p.delete_annot(p.load_annot(xref))
        self.dirty = True
        return {'dirty': True}

    def save(self, path, expected=None):
        target = Path(path).expanduser().absolute()
        # Resolve an existing symlink instead of replacing the link itself.
        target = target.resolve()
        original = target == self.path
        if original and fingerprint(target) != self.stamp:
            raise ValueError('El archivo cambió fuera de Wysun. Guarda una copia para conservar ambas versiones.')
        if not original and target.exists() and (expected is None or list(fingerprint(target)) != expected):
            raise ValueError('El destino cambió. Vuelve a seleccionar dónde guardar.')
        with atomic_path(target) as temporary:
            self.doc.save(temporary, garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            if original and fingerprint(target) != self.stamp:
                raise ValueError('El original cambió durante el guardado. Guarda una copia.')
            if not original and target.exists() and (expected is None or list(fingerprint(target)) != expected):
                raise ValueError('El destino cambió durante el guardado.')
        self.path, self.stamp = target, fingerprint(target)
        self.dirty = False
        return {'path': str(target), 'dirty': False}


def _excerpt(line, term):
    """The line around the first occurrence of ``term``, at most CONTEXT characters."""
    if len(line) <= CONTEXT:
        return line
    at = max(0, line.lower().find(term.lower()))
    start = max(0, min(at - CONTEXT // 3, len(line) - CONTEXT + 2))
    text = line[start:start + CONTEXT - 2]
    return ('…' if start else '') + text + ('…' if start + len(text) < len(line) else '')


def main():
    engine = PdfEngine()
    out = sys.stdout.buffer
    for line in sys.stdin:
        blob = b''
        try:
            request = json.loads(line)
            operation = request['op']
            if operation not in OPERATIONS:
                raise ValueError('Operación desconocida')
            result = getattr(engine, operation)(**request.get('args', {}))
            blob = result.pop('_blob', b'')
            reply = {'result': result, 'blob': len(blob)}
        except Exception as exc:
            reply = {'error': str(exc)}
        # One JSON line, then exactly ``blob`` raw bytes when the reply carries pixels.
        out.write((json.dumps(reply) + '\n').encode())
        out.write(blob)
        out.flush()
    if engine.doc:
        engine.doc.close()


if __name__ == '__main__':
    main()
