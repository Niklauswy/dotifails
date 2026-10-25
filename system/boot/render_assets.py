#!/usr/bin/env python3
"""Wysun boot art: GRUB (the training tape's title card) and Plymouth (the office terminal), Severance tokens.

The installer ships the results; a new machine needs none of this. To regenerate (inside a Wysun
session, with the shell runtime installed):

    python3 system/boot/render_assets.py

The title card, the terminal, the project index, Cold Harbor opening, the data field, the passphrase program
and the cursor are rendered by Quickshell with the
boot shaders (apps/shell/modules/bootart); GRUB's frames and bars and the gauge are
painted here with Qt, and GRUB's sans fonts are built from DejaVu with grub-mkfont. Colours come only from apps/shell/modules/lockscreen/severance-scheme.json, and
GRUB's theme.txt and Plymouth's script are written from their templates with those colours.
GRUB decodes PNGs slowly, so its images must stay small: the build fails if the background grows.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BOOT = ROOT / 'system/boot'
SHELL = ROOT / 'apps/shell'
RUNTIME = Path(os.environ.get('WYSUN_RUNTIME', Path.home() / '.local/share/wysun/runtime'))
GRUB_BACKGROUND_LIMIT = 400 * 1024
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import theme_core  # noqa: E402

# The boot art always wears the Severance palette of the lock (the desktop's colours follow the
# wallpaper, the office terminal does not). Only the fonts come from the theme tokens.
TOKENS = theme_core.resolve()
SEVERANCE = json.loads((SHELL / 'modules/lockscreen/severance-scheme.json').read_text())['colours']
# The training tape's blue is a reference colour of the boot art, not part of any desktop theme.
CARD = '#2338D2'  # theme-exception: the title card's broadcast blue
PALETTE = {**{name: '#' + value for name, value in SEVERANCE.items()}, 'card': CARD}
MONO = TOKENS['font_mono'][0]
SANS = TOKENS['font_family'][0]
# GRUB fonts: (file, DejaVu face, size). The menu speaks the title card's bold sans.
GRUB_FONTS = (('sans-bold-22.pf2', 'DejaVuSans-Bold.ttf', 22), ('sans-bold-16.pf2', 'DejaVuSans-Bold.ttf', 16))
DEJAVU = Path('/usr/share/fonts/truetype/dejavu')


def hex6(value):
    return value.lstrip('#')[:6].lower()


def rgb(value):
    value = hex6(value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def render_with_shaders(out, farewell_only=False):
    qsb = next(RUNTIME.glob('qt/*/gcc_64/bin/qsb'))
    shaders = out / 'shaders'
    shaders.mkdir()
    # The mascot lives with the lock (it is also the lock's easter egg); the rest is boot-only.
    for name, module in (('crt', 'bootart'), ('filebox', 'bootart'), ('vhs', 'bootart'), ('phosphor', 'bootart'),
                         ('mascot', 'lockscreen')):
        subprocess.run([str(qsb), '--glsl', '300es,330', '-o', str(shaders / f'{name}.frag.qsb'),
                        str(SHELL / f'modules/{module}/shaders/{name}.frag')], check=True)
    scheme = out / 'scheme.json'
    scheme.write_text(json.dumps({'name': 'severance', 'flavour': 'boot', 'mode': 'dark', 'variant': 'tonalspot',
                                  'colours': {key: hex6(value) for key, value in PALETTE.items()}}))
    env = dict(os.environ, WYSUN_SHELL_ENTRY=str(SHELL / 'boot-art.qml'), WYSUN_BOOT_ART_OUT=str(out),
               WYSUN_BOOT_ART_SHADERS=str(shaders), WYSUN_BOOT_ART_SCHEME=str(scheme), WYSUN_BOOT_ART_MONO=MONO,
               WYSUN_BOOT_ART_SANS=SANS)
    if farewell_only:
        env["WYSUN_BOOT_FAREWELL_ONLY"] = "1"
    subprocess.run(['sh', str(SHELL / 'wysun/runtime.sh')], env=env, check=True, timeout=900,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    missing = [name for name in ('grub-background', 'plymouth-background', 'pointer', 'card-5', 'flip-4-4', 'fade-4', 'pass-16', 'field-b', 'status-ready', 'glyph-colon')
               if not (out / f'{name}.png').is_file()]
    if farewell_only:
        missing = [name for name in ("mascot-walk-r-11", "mascot-hop-9", "balloon-goodbye", "shadow", "status-closing", "status-reboot") if not (out / f"{name}.png").is_file()]
    if missing:
        raise SystemExit('Quickshell did not render: ' + ', '.join(missing))


def draw_pieces(out):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen
    QGuiApplication.instance() or QGuiApplication(['boot-art', '-platform', 'offscreen'])

    def colour(token, alpha=255):
        value = QColor(*rgb(PALETTE[token]))
        value.setAlpha(alpha)
        return value

    def image(width, height):
        result = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        result.fill(Qt.transparent)
        return result

    def nine_slice(name, fill, border, size=12, line=2):
        full = image(size * 3, size * 3)
        painter = QPainter(full)
        painter.fillRect(full.rect(), fill)
        if border is not None:
            painter.setPen(QPen(border, line))
            painter.drawRect(QRectF(line / 2, line / 2, size * 3 - line, size * 3 - line))
        painter.end()
        for row, vertical in enumerate(('n', '', 's')):
            for column, horizontal in enumerate(('w', '', 'e')):
                part = (vertical + horizontal) or 'c'
                full.copy(column * size, row * size, size, size).save(str(out / f'{name}_{part}.png'))

    # GRUB: the programs are printed on the card; the chosen one is a solid white bar with blue text.
    nine_slice('menu', QColor(Qt.transparent), None)
    nine_slice('select', colour('onSurface'), None, size=6)
    nine_slice('bar', QColor(Qt.transparent), colour('onSurface', 200), size=6)
    nine_slice('bar-fill', colour('onSurface', 70), None, size=6)

    # Plymouth: the header gauge's fill.
    fill = image(8, 21)
    fill.fill(colour('info', 210))
    for row in range(2, 21, 3):  # the phosphor's scanlines, kept when Plymouth stretches it sideways
        for column in range(8):
            fill.setPixelColor(column, row, colour('info', 110))
    fill.save(str(out / 'fill.png'))



def terminal_box(grub):
    """GRUB's terminal box is the card itself: its centre is the background's own pixels under the box and
    its edges are invisible, so boot messages appear printed on the card instead of in a black box. GRUB
    scales the background and the box alike, so they stay aligned at any resolution."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage
    QGuiApplication.instance() or QGuiApplication(['boot-art', '-platform', 'offscreen'])
    background = QImage(str(grub / 'background.png')).convertToFormat(QImage.Format_RGB32)
    left, top = round(background.width() * 0.18), round(background.height() * 0.46)
    width, height = round(background.width() * 0.64), round(background.height() * 0.44)
    background.copy(left + 1, top + 1, width - 2, height - 2).save(str(grub / 'term_c.png'))
    edge = QImage(1, 1, QImage.Format_ARGB32)
    edge.fill(Qt.transparent)
    for part in ('nw', 'n', 'ne', 'w', 'e', 'sw', 's', 'se'):
        edge.save(str(grub / f'term_{part}.png'))


def build_fonts():
    """GRUB's bitmap fonts from DejaVu (license in grub/FONT-LICENSE); only the glyphs the menu needs."""
    ranges = '0x20-0x7E,0xA0-0x17F,0x2022-0x2022,0x2190-0x2193'
    for name, face, size in GRUB_FONTS:
        subprocess.run(['grub-mkfont', '-s', str(size), '-r', ranges, '-o', str(BOOT / 'grub' / name),
                        str(DEJAVU / face)], check=True)


def write_templates():
    def css(token):
        return '#' + hex6(PALETTE[token])

    def floats(token):
        return ', '.join(f'{channel / 255:.4f}' for channel in rgb(PALETTE[token]))

    values = {
        'BASE': css('surface'), 'INK': css('primary'), 'TEXT': css('onSurface'), 'MUTED': css('onSurfaceVariant'),
        'BASE_RGB': floats('surface'), 'INK_RGB': floats('primary'), 'TEXT_RGB': floats('onSurface'),
        'DANGER_RGB': floats('error'), 'MUTED_RGB': floats('onSurfaceVariant'), 'MONO': MONO,
        'CARD': css('card'), 'INFO_RGB': floats('info'), 'SANS': SANS,
    }
    for template, target in ((BOOT / 'grub/theme.txt.in', BOOT / 'grub/theme.txt'),
                             (BOOT / 'plymouth/orbit.script.in', BOOT / 'plymouth/orbit.script')):
        text = template.read_text()
        for key, value in values.items():
            text = text.replace('@' + key + '@', value)
        target.write_text(text)


def optimise(path):
    """Keep GRUB's PNGs small: 8-bit palette when Qt can, never above the limit."""
    from PySide6.QtGui import QImage
    image = QImage(str(path)).convertToFormat(QImage.Format_RGB32)
    image.save(str(path), 'PNG', 0)


def main():
    with tempfile.TemporaryDirectory(prefix='wysun-boot-art-') as folder:
        out = Path(folder)
        farewell_only = '--farewell-only' in sys.argv
        render_with_shaders(out, farewell_only)
        if farewell_only:
            for path in out.glob('*.png'):
                shutil.copy(path, BOOT / 'plymouth' / path.name)
            write_templates()
            print('Farewell mascot and captions written; existing monitor art preserved.')
            return
        draw_pieces(out)
        grub, plymouth = BOOT / 'grub', BOOT / 'plymouth'
        for stale in [*grub.glob('*.png'), *plymouth.glob('*.png')]:
            stale.unlink()
        shutil.copy(out / 'grub-background.png', grub / 'background.png')
        optimise(grub / 'background.png')
        size = (grub / 'background.png').stat().st_size
        if size > GRUB_BACKGROUND_LIMIT:
            raise SystemExit(f'grub/background.png is {size // 1024} KB; GRUB would load it slowly (limit '
                             f'{GRUB_BACKGROUND_LIMIT // 1024} KB). Keep the card free of grain.')
        terminal_box(grub)
        for name in ('menu', 'select', 'bar', 'bar-fill'):
            for path in out.glob(name + '_*.png'):
                shutil.copy(path, grub / path.name)
        shutil.copy(out / 'plymouth-background.png', plymouth / 'background.png')
        captions = [path.stem for pattern in ('status-*', 'glyph-*', 'card-*', 'flip-*', 'fade-*', 'field-*', 'pass-*', 'mascot-*',
                                                     'balloon-*', 'shadow')
                    for path in out.glob(pattern + '.png')]
        for name in ('fill', 'pointer', 'click', 'dialog', *captions):
            shutil.copy(out / f'{name}.png', plymouth / f'{name}.png')
    for stale in (BOOT / 'grub').glob('*.pf2'):
        if stale.name != 'mono-16.pf2':
            stale.unlink()
    build_fonts()
    write_templates()
    print('Boot art written to', BOOT, f'(GRUB background {size // 1024} KB)')


if __name__ == '__main__':
    main()
