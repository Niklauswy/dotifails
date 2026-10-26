"""Capture matrix of the gallery (not a test): every page x style x palette x mode, offscreen.

    <qml-runtime>/bin/python3 tests/qml/capture_matrix.py OUT [--pages theme,buttons] [--scale 0.5]

Writes OUT/<style>/<palette>-<mode>/<page>.png, one montage per palette (OUT/montage-<palette>.png: pages as rows,
light and dark side by side) and OUT/index.json. When the user's live scheme.json exists it is added as the
"wallpaper" palette (read only; it is not part of the tests).
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'apps/python/vendor'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('WYSUN_QML_LIB', str(ROOT / 'apps/qml'))

from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()


def main(argv=None):
    from wysun_qml import gallery
    from qml import support
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--pages', default=','.join(gallery.PAGES))
    parser.add_argument('--scale', type=float, default=0.5)
    parser.add_argument('--width', type=int, default=1000)
    parser.add_argument('--height', type=int, default=760)
    args = parser.parse_args(argv)
    pages = [p for p in args.pages.split(',') if p]

    from types import SimpleNamespace
    from PySide6 import QtQuick  # noqa: F401
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEvent, Qt
    from PySide6.QtGui import QImage, QPainter
    from wysun_core import theme

    options = SimpleNamespace(page=pages[0], palette='default', mode='dark', width=args.width, height=args.height,
                              bench=False, reduced_motion=True)
    app, engine, window, controller = gallery.build(options)

    def pump(ms):
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < ms:
            QCoreApplication.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)     # outgoing pages (no exec loop)

    palettes = {name: ('light', 'dark') for name in ('default', *gallery.SEEDS)}
    if (Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'wysun/scheme.json').exists():
        palettes['wallpaper'] = (theme.active_scheme()['mode'],)

    index = []
    for style in support.STYLES:
        for name, modes in palettes.items():
            for mode in modes:
                controller.setPalette('live' if name == 'wallpaper' else name)
                controller.setMode('' if name == 'wallpaper' else mode)
                for page in pages:
                    support.Harness.call(None, window, "showPage", page)
                    pump(150)
                    target = args.out / style / f'{name}-{mode}' / f'{page}.png'
                    target.parent.mkdir(parents=True, exist_ok=True)
                    window.grabWindow().save(str(target))
                    index.append({'style': style, 'palette': name, 'mode': mode, 'page': page,
                                  'path': str(target.relative_to(args.out))})

        for name, modes in palettes.items():
            w, h = int(args.width * args.scale), int(args.height * args.scale)
            columns = list(modes)
            montage = QImage(w * len(columns), h * len(pages), QImage.Format_RGB32)
            painter = QPainter(montage)
            for col, mode in enumerate(columns):
                for row, page in enumerate(pages):
                    shot = QImage(str(args.out / style / f'{name}-{mode}' / f'{page}.png'))
                    painter.drawImage(col * w, row * h, shot.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            painter.end()
            montage.save(str(args.out / f'montage-{name}.png'))

    (args.out / 'index.json').write_text(json.dumps(index, indent=1))
    print(f'{len(index)} captures in {args.out}')
    window.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
