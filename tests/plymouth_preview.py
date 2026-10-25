#!/usr/bin/env python3
"""Run Wysun's Plymouth script in the real Plymouth interpreter and paint what it would show.

Display-only doubles record every sprite (image, scale, position, opacity, z); Qt then composites
the frame with the theme's real PNGs. Nothing is shown on a console and nothing needs root.

    python3 tests/plymouth_preview.py OUT_DIR

Writes boot-start, boot-progress, password, shutdown-drain and shutdown-off frames.
"""
import ctypes as C
import json
from pathlib import Path
import re
import sys

SOURCE = Path(__file__).resolve().parents[1]
THEME = SOURCE / 'system/boot/plymouth'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plymouth_runtime import Engine  # noqa: E402

WIDTH, HEIGHT = 1920, 1080
RECORDING = '''
fun noop() {}
Window.GetWidth=fun () { return %d; };
Window.GetHeight=fun () { return %d; };
Window.GetX=fun () { return 0; };
Window.GetY=fun () { return 0; };
Window.SetBackgroundTopColor=noop;
Window.SetBackgroundBottomColor=noop;
fun make_image(name) {
    local.picture.name=name;
    picture.w=-1; picture.h=-1;
    if (global.natural_w[name]) { picture.w=global.natural_w[name]; picture.h=global.natural_h[name]; }
    picture.Scale=fun (w,h) { local.copy=make_image(this.name); copy.w=w; copy.h=h; return copy; };
    picture.GetWidth=fun () { return this.w; };
    picture.GetHeight=fun () { return this.h; };
    return picture;
}
fun font_size(font) {
    local.size=0; local.scale=1; local.done=0;
    for (local.i=String(font).Length()-1; i>=0; i--) {
        local.c=String(font).CharAt(i);
        local.digit=-1;
        for (local.k=0; k<10; k++) if ("0123456789".CharAt(k)==c) digit=k;
        if (digit<0) done=1;
        if (!done) { size+=digit*scale; scale*=10; }
    }
    return size;
}
Image.Text=fun (text,r,g,b,a,font) {
    local.picture=make_image("text:" + text);
    picture.text=text; picture.r=r; picture.g=g; picture.b=b; picture.font=font;
    picture.w=String(text).Length() * font_size(font) * 0.8; picture.h=font_size(font) * 1.6;
    return picture;
};
Image |= make_image;
sprite_total=0;
fun Sprite(image) {
    local.sprite.image=image;
    sprite.x=0; sprite.y=0; sprite.z=0; sprite.opacity=1;
    sprite.SetImage=fun (image) { this.image=image; };
    sprite.SetPosition=fun (x,y,z) { this.x=x; this.y=y; this.z=z; };
    sprite.SetOpacity=fun (value) { this.opacity=value; };
    sprite.SetZ=fun (z) { this.z=z; };
    global.sprite_list[global.sprite_total]=sprite;
    global.sprite_total++;
    return sprite;
}
Plymouth.GetMode=fun () { return global.test_mode; };
Plymouth.SetRefreshFunction=noop;
Plymouth.SetBootProgressFunction=noop;
Plymouth.SetDisplayPasswordFunction=noop;
Plymouth.SetDisplayQuestionFunction=noop;
Plymouth.SetDisplayNormalFunction=noop;
Plymouth.SetDisplayMessageFunction=noop;
Plymouth.SetHideMessageFunction=noop;
Plymouth.SetMessageFunction=noop;
Plymouth.SetQuitFunction=noop;
fun dump() {
    local.out="";
    for (local.i=0; i<sprite_total; i++) {
        local.s=sprite_list[i];
        if (s.image) {
            local.p=s.image;
            out+=p.name + "|" + p.w + "|" + p.h + "|" + s.x + "|" + s.y + "|" + s.z + "|" + s.opacity;
            if (p.text) out+="|" + p.r + "|" + p.g + "|" + p.b + "|" + p.font;
            out+="\\n";
        }
    }
    global.dump_result=out;
}
''' % (WIDTH, HEIGHT)


def natural_sizes():
    """The theme's PNG sizes, so the script centres pre-rendered images as Plymouth would."""
    from PySide6.QtGui import QImageReader
    lines = []
    for path in sorted(THEME.glob('*.png')):
        size = QImageReader(str(path)).size()
        lines.append(f'natural_w["{path.name}"]={size.width()}; natural_h["{path.name}"]={size.height()};')
    return '\n'.join(lines) + '\n'


def run(mode, steps):
    engine = Engine()
    try:
        engine.execute(natural_sizes() + RECORDING + '\ntest_mode="' + mode + '";\n' + (THEME / 'orbit.script').read_text())
        for step in steps:
            engine.execute(step)
        engine.execute('dump();')
        return engine.string('dump_result') or ''
    finally:
        engine.close()


def records(dump):
    for line in dump.splitlines():
        parts = line.split('|')
        record = dict(name=parts[0], w=float(parts[1]), h=float(parts[2]), x=float(parts[3]), y=float(parts[4]),
                      z=float(parts[5]), opacity=float(parts[6]))
        if len(parts) > 7:
            record.update(r=float(parts[7]), g=float(parts[8]), b=float(parts[9]), font=parts[10])
        yield record


def paint(dump, target):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
    QGuiApplication.instance() or QGuiApplication(['plymouth-preview', '-platform', 'offscreen'])
    canvas = QImage(WIDTH, HEIGHT, QImage.Format_RGB32)
    canvas.fill(Qt.black)
    painter = QPainter(canvas)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    cache = {}
    for record in sorted(records(dump), key=lambda item: item['z']):
        if record['opacity'] <= 0:
            continue
        painter.setOpacity(min(1.0, record['opacity']))
        if record['name'].startswith('text:'):
            size = int(re.findall(r'(\d+)$', record['font'])[0]) if re.search(r'\d+$', record['font']) else 18
            font = QFont(record['font'].rsplit(' ', 1)[0])
            font.setPixelSize(round(size * 1.33))
            painter.setFont(font)
            painter.setPen(QColor.fromRgbF(record['r'], record['g'], record['b']))
            painter.drawText(QRectF(record['x'], record['y'], 2000, size * 2), Qt.AlignLeft | Qt.AlignTop, record['name'][5:])
            continue
        image = cache.get(record['name'])
        if image is None:
            image = cache[record['name']] = QImage(str(THEME / record['name']))
        width = record['w'] if record['w'] >= 0 else image.width()
        height = record['h'] if record['h'] >= 0 else image.height()
        painter.drawImage(QRectF(record['x'], record['y'], width, height), image)
    painter.end()
    canvas.save(str(target))


FRAMES = {
    'boot-start': ('boot', ['for (j=0;j<60;j++) refresh();']),
    'boot-progress': ('boot', ['boot_progress(10, 0.52); for (j=0;j<80;j++) refresh();']),
    'boot-open': ('boot', ['boot_progress(10, 1); for (j=0;j<160;j++) refresh();']),
    'password': ('boot', ['boot_progress(10, 0.2); for (j=0;j<30;j++) refresh();',
                          'password("Please unlock disk nvme0n1p3_crypt", 6); refresh();']),
    'shutdown-closing': ('shutdown', ['for (j=0;j<180;j++) refresh();']),
    'shutdown-end': ('shutdown', ['for (j=0;j<600;j++) refresh();']),
}

if __name__ == '__main__':
    out = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    out.mkdir(parents=True, exist_ok=True)
    for name, (mode, steps) in FRAMES.items():
        paint(run(mode, steps), out / f'{name}.png')
        print('ok', name)
