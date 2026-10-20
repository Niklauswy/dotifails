"""Offscreen acceptance probe; use temporary HOME/XDG and optional snapshot dir.

No compositor, network, audio device, installer or installed application is used.
Run through test_music_material.py for isolation, or supply an isolated environment
and MUSIC_SNAPSHOT_DIR to retain seven labelled synthetic screenshots.
"""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QColor, QFont, QRawFont, QTextLayout
from PySide6.QtWidgets import QApplication, QWidget
import music_data as music
import theme_core
from theme_tokens import tokens, watch_theme
from music_material import (SYMBOLS, display_family, ligature_available,
                            load_fonts, material_icon, symbol_family)
from music_app_window import MusicAppWindow
from music_mini import MiniPlayer
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
window = MusicAppWindow(test=True)
window.show()
app.processEvents()
keys = window.all_keys()
assert len(keys) == 2
window.covers[keys[0]] = str(cover)
window.current_key = keys[0]
window.current_audio = window.playable(keys[0])
window.show_current()
mini = MiniPlayer(window)
mini.show()
mini.sync()
assert 'Rubik' in load_fonts() and 'Material Symbols Rounded' in load_fonts()
assert display_family() == 'Rubik' and symbol_family() == 'Material Symbols Rounded'
assert window.now_title.font().family() == 'Rubik'
raw = QRawFont.fromFont(QFont('Rubik'))
assert raw.supportsCharacter(ord('ñ')) and raw.supportsCharacter(ord('ú'))
# Offline subset must render its bundled ligature as one glyph, and every
# requested symbol must still yield a visible icon through the Lucide fallback.
layout = QTextLayout('volume_up', QFont('Material Symbols Rounded'))
layout.beginLayout(); layout.createLine(); layout.endLayout()
assert sum(len(run.glyphIndexes()) for run in layout.glyphRuns()) == 1
assert ligature_available('volume_up')
assert not ligature_available('definitely_not_a_material_ligature')
for symbol in SYMBOLS:
    assert not material_icon(symbol).isNull(), symbol
assert not window.play_button.icon().isNull()
assert not window.nav.item(0).icon().isNull()

before_library = (music.DATA / 'library.json').read_bytes()
window.order.start(keys, keys[0], True)
window.queue = window.order.keys.copy()
queue = window.order.export()
window.favorite(keys[0])
window.go('favorites')
assert window.tree.topLevelItemCount() == 1
window.search.setText('Segunda')
assert window.tree.topLevelItemCount() == 1
assert window.tree.topLevelItem(0).data(0, Qt.UserRole) == keys[1]
assert window.order.export() == queue
window.search.clear()
window.go('home')
assert window.pages.currentWidget() is window.tree

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
    # The scheme file is the dynamic colour authority; the selection still
    # chooses a known preset geometry until theme_core exposes "dynamic" itself.
    schemes.append(('material-you-' + mode, {'style': 'fluent', 'variant': mode},
                    generate_dynamic(cover, mode=mode)))
for name, chosen, scheme in schemes:
    # Same contract/atomic replace as the existing producer; no second authority.
    selection.write_text(json.dumps(chosen))
    temporary = scheme_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(scheme))
    temporary.replace(scheme_path)
    # onSurfaceVariant maps to ``muted`` and has no later role overriding it;
    # ``canvas`` intentionally takes the strongest surface container instead.
    wait_for(lambda: tokens()['muted'].lower().lstrip('#') == scheme['colours']['onSurfaceVariant'].lower(),
             f'{name}: tokens did not adopt scheme onSurfaceVariant ({tokens()["muted"]})')
    wait_for(lambda: tokens()['text'].lower() in window.styleSheet().lower(),
             f'{name}: window stylesheet did not re-render')
    assert window.order.export() == queue
    assert window.favorite_keys == {keys[0]}
    for width, height in ((1180, 760), (900, 660), (820, 600)):
        window.resize(width, height)
        app.processEvents()
        assert window.width() == width, (name, 'unexpected minimum width', window.width())
        art = window.hero_cover.mapTo(window, QPoint())
        tracks = window.tree.mapTo(window, QPoint())
        navigation = window.sidebar.mapTo(window, QPoint())
        transport = window.player_panel.mapTo(window, QPoint())
        assert navigation.x() < art.x() < tracks.x()
        assert art.y() < tracks.y() + window.tree.height()
        assert window.hero_cover.width() >= 200
        assert transport.y() >= window.center.geometry().bottom()
        assert window.tree.viewport().width() >= 200
        assert window.tree.horizontalScrollBar().maximum() == 0
        assert window.play_button.isEnabled()
        for control in (window.play_button, window.previous_button, window.next_button, window.volume):
            point = control.mapTo(window, QPoint())
            assert window.rect().contains(point) and window.rect().contains(point + control.rect().bottomRight())
        if snapshots and width == 1180:
            assert window.grab().save(str(Path(snapshots) / (name + '.png')))
    # Empty and gallery routes remain reachable without modifying queue or library.
    window.go('albums'); assert window.pages.currentIndex() == 3
    window.search.setText('sin coincidencias'); assert window.pages.currentIndex() == 5
    window.go('home')

window.show_lyrics({'synced': '[00:00]Primera línea\n[00:01]Segunda línea'})
assert window.lyric_list.count() == 2
window.lyrics_panel.show();window.adapt_lyrics();app.processEvents()
assert window.lyrics_panel.isVisible()
window.lyrics_panel.hide();window.adapt_lyrics()
window.status.setText('Aviso de prueba');assert window.status.isVisible()
window.current_position = 1.25
window.volume.setValue(37)
window.repeat.setChecked(True)
window.test = False
window.save_session()
window.test = True
saved = window.store.get('session')
assert saved['position'] == 1.25 and saved['volume'] == 37
assert saved['order'] == queue and saved['repeat'] is True
assert (music.DATA / 'library.json').read_bytes() == before_library
window.shutdown_jobs();window.store.close();window.hide()
restored = MusicAppWindow(test=True)
assert restored.current_key == keys[0] and restored.current_position == 1.25
assert restored.volume.value() == 37 and restored.repeat.isChecked()
assert restored.order.export() == queue and restored.favorite_keys == {keys[0]}
restored.shutdown_jobs();restored.store.close()
mini.timer.stop();mini.hide()
print('MUSIC_MATERIAL_OK: seven schemes, live watcher, offline fonts, three sizes, queue, favorites, lyrics, session restoration')
