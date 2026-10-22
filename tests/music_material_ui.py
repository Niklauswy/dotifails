"""Offscreen acceptance probe; use temporary HOME/XDG and optional snapshot dir.

No compositor, network, audio device, installer or installed application is used.
Run through test_music_material.py for isolation, or supply an isolated environment
and MUSIC_SNAPSHOT_DIR to keep labelled synthetic screenshots per scheme.
"""
import json
import os
from pathlib import Path
import sys
import time
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QFont, QImage, QRawFont, QTextLayout
from PySide6.QtWidgets import QApplication
import music_data as music
import theme_core
from music_material import display_family, ligature_available, load_fonts, symbol_family
from theme_tokens import tokens, watch_theme
from wysun_scheme import fixed_scheme, generate_dynamic

app = QApplication([])
app.setStyle('Fusion')
assert Path.home() != Path('/root'), 'Use an isolated HOME'
image = QImage(256, 256, QImage.Format_RGB32)
image.fill(QColor('#397d8d'))  # theme-exception: synthetic cover/seed, user image data
cover = Path.home() / 'synthetic-cover.png'
assert image.save(str(cover))
for name in ('Primera', 'Segunda'):
    with wave.open(str(Path.home() / (name + '.wav')), 'wb') as output:
        output.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        output.writeframes(b'\0\0' * 16000)
music.import_files([Path.home() / 'Primera.wav', Path.home() / 'Segunda.wav'])
selection = theme_core.selection_path()
selection.parent.mkdir(parents=True, exist_ok=True)
selection.write_text(json.dumps({'style': 'fluent', 'variant': 'dark'}))
scheme_path = theme_core.scheme_path()
scheme_path.parent.mkdir(parents=True, exist_ok=True)
watch_theme()

from wysun_music.app import build  # noqa: E402  (after the isolated theme exists)

music_app = build(persist=True, network=False, publish=False)
window, player, library, covers = music_app.window, music_app.player, music_app.library, music_app.covers
window.show()
app.processEvents()
keys = library.all_keys()
assert len(keys) == 2
covers._paths[keys[0]] = str(cover)  # synthetic artwork, as a finished lookup would leave it

# Offline fonts: Rubik text, Material Symbols ligatures rendered as single glyphs.
assert 'Rubik' in load_fonts() and 'Material Symbols Rounded' in load_fonts()
assert display_family() == 'Rubik' and symbol_family() == 'Material Symbols Rounded'
assert window.font().family() == 'Rubik' and window.bar.title.font().family() == 'Rubik'
raw = QRawFont.fromFont(QFont('Rubik'))
assert raw.supportsCharacter(ord('ñ')) and raw.supportsCharacter(ord('ú'))
layout = QTextLayout('volume_up', QFont('Material Symbols Rounded'))
layout.beginLayout(); layout.createLine(); layout.endLayout()
assert sum(len(run.glyphIndexes()) for run in layout.glyphRuns()) == 1
assert ligature_available('volume_up') and not ligature_available('definitely_not_a_material_ligature')

# Browsing never touches the queue or the download manifest.
before_library = (music.DATA / 'library.json').read_bytes()
player.play_collection(keys, keys[0], 'all')
player.engine.quit()  # no audio device needed for presentation checks
queue = player.queue.export()
library.toggle_favorite(keys[0])
window.navigate(('collection', 'favorites'))
assert window.collection.tracks.keys == [keys[0]]
window.search.setText('Segunda')
window.search_page.set_query('Segunda')
assert window.search_page.songs.keys == [keys[1]]
assert player.queue.export() == queue
window.navigate(('home',))
assert window.pages.currentWidget() is window.home

snapshots = os.environ.get('MUSIC_SNAPSHOT_DIR')
if snapshots:
    Path(snapshots).mkdir(parents=True, exist_ok=True)


def wait_for(predicate, detail='Theme observer did not update Music'):
    until = time.monotonic() + 3
    while time.monotonic() < until:
        app.processEvents()
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError(detail)


schemes = [(f'{style}-{variant}', {'style': style, 'variant': variant}, fixed_scheme(style, variant))
           for style, variant in (('space-black', 'space-black'), ('space-black', 'tokyo'),
                                  ('space-black', 'severance'), ('fluent', 'light'), ('fluent', 'dark'))]
for mode in ('light', 'dark'):
    schemes.append(('material-you-' + mode, {'style': 'fluent', 'variant': mode}, generate_dynamic(cover, mode=mode)))
for name, chosen, scheme in schemes:
    selection.write_text(json.dumps(chosen))
    temporary = scheme_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(scheme))
    temporary.replace(scheme_path)
    wait_for(lambda: tokens()['muted'].lower().lstrip('#') == scheme['colours']['onSurfaceVariant'].lower(),
             f'{name}: tokens did not adopt scheme onSurfaceVariant ({tokens()["muted"]})')
    wait_for(lambda: tokens()['text'].lower() in window.styleSheet().lower(), f'{name}: window stylesheet did not re-render')
    assert player.queue.export() == queue and library.favorites == {keys[0]}
    for route in (('home',), ('collection', 'all'), ('search', ''), ('downloads',), ('artists',), ('albums',)):
        window.navigate(route)
        for width, height in ((1280, 820), (1000, 680), (900, 600)):
            window.resize(width, height)
            app.processEvents()
            assert window.width() == width, (name, 'unexpected minimum width', window.width())
            sidebar = window.sidebar.mapTo(window, QPoint())
            main = window.main.mapTo(window, QPoint())
            bar = window.bar.mapTo(window, QPoint())
            assert sidebar.x() < main.x() and window.main.width() >= 400, (name, route, width)
            assert bar.y() >= main.y() + window.main.height(), (name, route, 'player bar overlaps content')
            for control in (window.bar.play, window.bar.previous, window.bar.next, window.bar.volume, window.search):
                point = control.mapTo(window, QPoint())
                assert window.rect().contains(point) and window.rect().contains(point + control.rect().bottomRight()), \
                    (name, route, width, control.accessibleName())
            if route == ('collection', 'all'):
                assert window.collection.tracks.horizontalScrollBar().maximum() == 0
            if snapshots and width == 1280:
                assert window.grab().save(str(Path(snapshots) / f'{name}-{route[0]}.png'))

# Side panel and lyrics fit next to the content without hiding the player bar.
window.resize(1280, 820)
window.toggle_panel('lyrics')
window.side.lyrics.set_lyrics({'synced': '[00:00]Primera línea\n[00:01]Segunda línea'})
app.processEvents()
assert window.side.isVisible() and len(window.side.lyrics.rows) == 2
window.toggle_panel('lyrics')
assert not window.side.isVisible()

# A song without lyrics shows what comes next instead of an empty column, and
# the lyrics tab returns on its own once a later song has them.
window.toggle_panel('now')
window.side.lyric_key = 'synthetic'
window.side._metadata_ready('lyrics', 'synthetic', {'unavailable': True})
assert window.side.current_tab() == 'queue' and window.side.queue.note.text()
window.side._metadata_ready('lyrics', 'synthetic', {'synced': '[00:00]Vuelve la letra'})
assert window.side.current_tab() == 'lyrics' and not window.side.queue.note.text()
window.toggle_panel(None)

# Session: position, volume, repeat and queue survive a restart; nothing autoplays.
player.position = 1.25
player.engine.volume = 37
player.set_repeat('all')
queue = player.queue.export()
player.save()
assert (music.DATA / 'library.json').read_bytes() == before_library
music_app.shutdown()
restored = build(persist=True, network=False, publish=False)
assert restored.player.current == keys[0] and restored.player.position == 1.25
assert restored.player.volume == 37 and restored.player.repeat == 'all'
assert restored.player.queue.export() == queue and restored.library.favorites == {keys[0]}
assert not restored.player.engine.running, 'Restoration unexpectedly started audio'
restored.shutdown()
print('MUSIC_MATERIAL_OK: seven schemes, live watcher, offline fonts, six routes × three sizes, full player, session restoration')
