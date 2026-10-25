#!/usr/bin/env python3
"""Paint Wysun's GRUB theme the way GRUB lays it out, from theme.txt, without rebooting.

    python3 tests/grub_preview.py OUT.png [WIDTH HEIGHT]

Supports what the theme uses: desktop-image, label, boot_menu (menu/selection 9-slices, fonts,
colours, item metrics) and the __timeout__ progress_bar. Entries are samples; the first is selected
and the countdown is shown at 5 of 10 seconds.
"""
import re
import sys
from pathlib import Path

THEME = Path(__file__).resolve().parents[1] / 'system/boot/grub'
import os
# Optional, for animations: GRUB_PREVIEW_SELECTED (entry index) and GRUB_PREVIEW_SECONDS (of a 10 s timeout).
SELECTED = int(os.environ.get('GRUB_PREVIEW_SELECTED', '0'))
SECONDS = float(os.environ.get('GRUB_PREVIEW_SECONDS', '5'))
ENTRIES = ('Parrot Security 7.4 (echo)', 'Advanced options for Parrot Security', 'Memory test (memtest86+x64.efi)',
           'UEFI Firmware Settings')


def parse(text):
    """theme.txt into (globals, [(component, {props})])."""
    settings, components = {}, []
    text = re.sub(r'^\s*#.*$', '', text, flags=re.M)
    for key, value in re.findall(r'^([\w-]+)\s*:\s*"?(.*?)"?\s*$', text, re.M):
        settings[key] = value
    for kind, body in re.findall(r'\+\s*(\w+)\s*\{(.*?)\}', text, re.S):
        props = dict((key, value.strip().strip('"')) for key, value in re.findall(r'([\w-]+)\s*=\s*("[^"]*"|[^\s]+)', body))
        components.append((kind, props))
    return settings, components


def length(value, total):
    total_value = 0.0
    for sign, number, percent in re.findall(r'([+-]?)\s*([\d.]+)(%?)', value):
        amount = float(number) * (total / 100 if percent else 1)
        total_value += -amount if sign == '-' else amount
    return total_value


def main():
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
    QGuiApplication.instance() or QGuiApplication(['grub-preview', '-platform', 'offscreen'])
    out = Path(sys.argv[1])
    width, height = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1920, 1080)
    settings, components = parse((THEME / 'theme.txt').read_text())
    canvas = QImage(width, height, QImage.Format_RGB32)
    canvas.fill(QColor(settings.get('desktop-color', '#000000')))  # theme-exception: reads the theme's own value
    painter = QPainter(canvas)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    painter.drawImage(QRectF(0, 0, width, height), QImage(str(THEME / settings['desktop-image'])))

    def font(spec):
        match = re.match(r'(.+?)\s+(Regular|Bold)?\s*(\d+)$', spec)
        result = QFont(match.group(1))
        result.setPixelSize(round(int(match.group(3)) * 1.0))
        result.setBold(match.group(2) == 'Bold')
        return result

    def nine(style, rect):
        prefix = style.replace('*.png', '')
        pieces = {part: QImage(str(THEME / f'{prefix}{part}.png')) for part in ('nw', 'n', 'ne', 'w', 'c', 'e', 'sw', 's', 'se')}
        side = pieces['nw'].width()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        painter.drawImage(QRectF(x + side, y + side, w - 2 * side, h - 2 * side), pieces['c'])
        painter.drawImage(QRectF(x + side, y, w - 2 * side, side), pieces['n'])
        painter.drawImage(QRectF(x + side, y + h - side, w - 2 * side, side), pieces['s'])
        painter.drawImage(QRectF(x, y + side, side, h - 2 * side), pieces['w'])
        painter.drawImage(QRectF(x + w - side, y + side, side, h - 2 * side), pieces['e'])
        for part, px, py in (('nw', x, y), ('ne', x + w - side, y), ('sw', x, y + h - side), ('se', x + w - side, y + h - side)):
            painter.drawImage(QRectF(px, py, side, side), pieces[part])

    for kind, props in components:
        rect = QRectF(length(props.get('left', '0'), width), length(props.get('top', '0'), height),
                      length(props.get('width', '0'), width), length(props.get('height', '0'), height))
        if kind == 'label':
            painter.setFont(font(props['font']))
            painter.setPen(QColor(props['color']))  # theme-exception: reads the theme's own value
            align = {'center': Qt.AlignHCenter, 'right': Qt.AlignRight}.get(props.get('align'), Qt.AlignLeft)
            painter.drawText(QRectF(rect.x(), rect.y(), rect.width(), 40), align | Qt.AlignTop, props['text'])
        elif kind == 'boot_menu':
            nine(props['menu_pixmap_style'], rect)
            item_height, padding = int(props['item_height']), int(props['item_padding'])
            spacing = int(props['item_spacing'])
            y = rect.y() + padding
            for index, entry in enumerate(ENTRIES):
                row = QRectF(rect.x() + padding, y, rect.width() - 2 * padding, item_height)
                selected = index == SELECTED
                if selected:
                    nine(props['selected_item_pixmap_style'], row)
                painter.setFont(font(props['selected_item_font' if selected else 'item_font']))
                painter.setPen(QColor(props['selected_item_color' if selected else 'item_color']))  # theme-exception: theme value
                painter.drawText(row.adjusted(padding, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, entry)
                y += item_height + spacing
        elif kind == 'progress_bar':
            nine(props['bar_style'], rect)
            nine(props['highlight_style'], QRectF(rect.x(), rect.y(), max(24, rect.width() * SECONDS / 10), rect.height()))
            painter.setFont(font(props['font']))
            painter.setPen(QColor(props['text_color']))  # theme-exception: reads the theme's own value
            painter.drawText(rect, Qt.AlignCenter, props['text'].replace('%d', str(round(SECONDS))))
    painter.end()
    canvas.save(str(out))


if __name__ == '__main__':
    main()
