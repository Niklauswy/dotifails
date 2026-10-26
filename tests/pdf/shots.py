"""Offscreen captures of the reader: base palettes and two synthetic wallpaper schemes, light and dark.

    /tmp/wysun-pdf-venv/bin/python tests/pdf/shots.py OUTPUT_DIR

Every capture runs in its own process with a temporary HOME/XDG tree; nothing of the user's is read or written.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
# theme-exception-begin: colores de fondos sintéticos para generar esquemas de prueba, no interfaz
WALLPAPERS = {'teal': ((14, 92, 98), (120, 200, 180)), 'amber': ((140, 60, 10), (240, 180, 70))}
# theme-exception-end
LOREM = ('Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt '
         'ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco.')


def sample(path):
    import fitz
    doc = fitz.open()
    for n in range(6):
        page = doc.new_page()
        page.insert_text((72, 96), f'Capítulo {n + 1}: Arquitectura de Wysun', fontsize=24)
        y = 140
        for line in range(26):
            start = (line * 13) % 90
            page.insert_text((72, y), LOREM[start:start + 82], fontsize=11)
            y += 22
        page.insert_text((72, y + 10), 'Un espacio tranquilo para leer y anotar.', fontsize=11)
    doc[0].insert_link({'kind': fitz.LINK_URI, 'uri': 'https://example.org', 'from': fitz.Rect(72, 730, 300, 745)})
    doc.set_toc([[1, f'Capítulo {n + 1}', n + 1] for n in range(6)])
    doc.save(path)
    doc.close()


def scheme(home, wallpaper, mode):
    sys.path.insert(0, str(APP))
    from PIL import Image
    from wysun_core import theme
    from wysun_services import scheme as wysun_scheme
    first, second = WALLPAPERS[wallpaper]
    image = Image.new('RGB', (96, 96))
    image.putdata([tuple(round(a + (b - a) * (x + y) / 190) for a, b in zip(first, second))
                   for y in range(96) for x in range(96)])
    source = Path(home) / f'{wallpaper}.png'
    image.save(source)
    theme.write_scheme(wysun_scheme.generate_dynamic(source, mode))


def capture(output, name):
    sys.path.insert(0, str(APP))
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    app.setStyle('Fusion')
    from wysun_pdf.window import PdfWindow

    def wait(condition, timeout=10):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            app.processEvents()
            time.sleep(.005)

    def settle():
        for _ in range(30):
            app.processEvents()
            time.sleep(.01)

    empty = PdfWindow()
    empty.resize(1280, 860)
    empty.show()
    settle()
    empty.grab().save(str(output / f'{name}-empty.png'))
    empty.close()

    document = Path(os.environ['HOME']) / 'muestra.pdf'
    sample(document)
    window = PdfWindow(str(document))
    window.resize(1280, 860)
    window.show()
    wait(window.ready)
    view = window.view
    wait(lambda: view.source.info(0) is not None)
    words = view.source.info(0)['words']
    start, end = words[6], words[18]
    for kind, word, buttons in ((QEvent.MouseButtonPress, start, Qt.LeftButton), (QEvent.MouseMove, end, Qt.LeftButton),
                                (QEvent.MouseButtonRelease, end, Qt.NoButton)):
        point = view.to_viewport(0, (word[0] + word[2]) / 2, (word[1] + word[3]) / 2)
        button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
        app.sendEvent(view.viewport(), QMouseEvent(kind, point, view.viewport().mapToGlobal(point), button, buttons, Qt.NoModifier))
    wait(lambda: len(window.sidebar.page_model.images) >= 4)
    settle()
    window.grab().save(str(output / f'{name}-reader.png'))
    window.study_note()
    window.notebook.editor.setPlainText('La idea central necesita una distinción: ¿qué cambia cuando leemos con una pregunta en mente?')
    window.notebook.save()
    settle()
    window.grab().save(str(output / f'{name}-notebook.png'))
    if name.startswith('base-'):
        window.resize(720, 480)
        settle()
        window.grab().save(str(output / f'{name}-narrow-notebook.png'))
        window.resize(1280, 860)
        settle()
    window.show_library()
    settle()
    window.grab().save(str(output / f'{name}-library.png'))
    from wysun_pdf.study_ui import StudySettings
    settings = StudySettings(window.preferences, window.study, window)
    settings.show()
    settle()
    settings.grab().save(str(output / f'{name}-settings.png'))
    settings.close()
    window.open_recent(str(document))
    window.toggle_notebook()
    window.toggle_focus()
    window.focus_panel.goal.setText('Entender el argumento central y formular una pregunta')
    window.focus_panel.toggle()
    window.focus_session.toggle()
    settle()
    window.grab().save(str(output / f'{name}-focus.png'))
    window.focus_session.finish()
    window.toggle_focus()
    window.consult_selection()
    window.lookup_panel.term.setText('justice')
    window.lookup_panel.results([dict(title='Justice · muestra de prueba', body='justicia',
        source='Proveedor simulado para captura', url='https://example.org/reference',
        attribution='Datos sintéticos · no es una consulta online')])
    settle()
    window.grab().save(str(output / f'{name}-lookup.png'))
    if name.startswith('base-'):
        window.resize(720, 480)
        settle()
        window.grab().save(str(output / f'{name}-narrow-lookup.png'))
        window.resize(1280, 860)
    window.hide_lookup()
    view.clear_selection()
    window.search.setText('tranquilo')
    window.start_search()
    wait(lambda: window.search_done)
    settle()
    window.grab().save(str(output / f'{name}-search.png'))
    window.clear_search()
    window.search.clear()
    window.set_view_mode('spread')
    window.fit('page')
    wait(window.ready)
    window.sidebar.set_tab(2)
    settle()
    window.grab().save(str(output / f'{name}-spread.png'))
    window.close()


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2:          # child: python shots.py OUTPUT NAME
        name = sys.argv[2]
        if os.environ.get('SHOT_WALLPAPER'):
            scheme(os.environ['HOME'], os.environ['SHOT_WALLPAPER'], os.environ['SHOT_MODE'])
        capture(output, name)
        return
    runs = [(f'base-{mode}', {'WYSUN_THEME': mode}) for mode in ('light', 'dark')]
    runs += [(f'{wallpaper}-{mode}', {'SHOT_WALLPAPER': wallpaper, 'SHOT_MODE': mode})
             for wallpaper in WALLPAPERS for mode in ('light', 'dark')]
    for name, extra in runs:
        with tempfile.TemporaryDirectory() as home:
            environment = {key: value for key, value in os.environ.items() if key != 'WYSUN_THEME'}
            environment.update(HOME=home, XDG_CONFIG_HOME=f'{home}/config', XDG_STATE_HOME=f'{home}/state',
                               XDG_DATA_HOME=f'{home}/data', XDG_CACHE_HOME=f'{home}/cache',
                               XDG_RUNTIME_DIR=f'{home}/runtime', QT_QPA_PLATFORM='offscreen',
                               WYSUN_REDUCED_MOTION='1', **extra)
            os.makedirs(f'{home}/runtime', mode=0o700)
            subprocess.run([sys.executable, __file__, str(output), name], env=environment, check=True)
            print('captura', name)


if __name__ == '__main__':
    main()
