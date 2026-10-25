"""Local PDF engine. Owned exclusively by the reader's worker process."""
import base64
import json
import math
from pathlib import Path
import sys

import fitz

from wysun_core.jsonio import atomic_path


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
            result = {'path': str(path), 'pages': candidate.page_count,
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

    def render(self, page, width):
        p = self.doc[page]
        # One raster at a time, at most 8 MP / 24 MB RGB, even for oversized PDFs.
        scale = min(max(200, min(width, 2800)) / p.rect.width,
                    math.sqrt(8_000_000 / (p.rect.width * p.rect.height)))
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        words = []
        for word in p.get_text('words', sort=True):
            rect = fitz.Rect(word[:4]) * p.rotation_matrix
            words.append([*rect, word[4]])
        annotations = [{'xref': a.xref, 'text': a.info.get('content') or a.type[1],
                        'type': a.type[1]} for a in p.annots() or ()]
        return {'page': page, 'width': p.rect.width, 'height': p.rect.height,
                'png': base64.b64encode(pix.tobytes('png')).decode('ascii'),
                'words': words, 'annotations': annotations}

    def thumbnail(self, page):
        p = self.doc[page]
        scale = min(160 / p.rect.width, 210 / p.rect.height)
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return {'page': page, 'png': base64.b64encode(pix.tobytes('png')).decode('ascii')}

    def search(self, page, text):
        p = self.doc[page]
        return {'page': page, 'hits': [list(r * p.rotation_matrix) for r in p.search_for(text)][:1000]}

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


def main():
    engine = PdfEngine()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            operation = request['op']
            if operation not in {'open', 'render', 'thumbnail', 'search', 'annotate', 'update_note', 'delete', 'save'}:
                raise ValueError('Operación desconocida')
            result = getattr(engine, operation)(**request.get('args', {}))
            reply = {'result': result}
        except Exception as exc:
            reply = {'error': str(exc)}
        print(json.dumps(reply), flush=True)
    if engine.doc:
        engine.doc.close()


if __name__ == '__main__':
    main()
