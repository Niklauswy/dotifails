"""Readers for text: a rendered Markdown document and a code view with gutter."""
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QGuiApplication, QPainter, QPixmap, QTextOption
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QSizePolicy, QTextEdit,
                               QVBoxLayout, QWidget)

from theme_tokens import color, on_theme_changed, tokens
from . import markdown
from .highlight import CodeHighlighter, highlight_html, language_for_fence, language_for_path, scheme
from .kit import IconButton, clip_pixmap, metric, text_font
from wysun_music.ui.shapes import squircle


def css(value):
    return f'rgba({value.red()},{value.green()},{value.blue()},{value.alpha()})'  # theme-exception: sintaxis rgba() de Qt CSS con un token (alfa 0-255)


def code_colors():
    """(background, text, line numbers) of code surfaces: the nvim scheme of the theme variant, else tokens."""
    nvim = scheme()
    if nvim:
        return QColor(nvim['base00']), QColor(nvim['base05']), QColor(nvim['gutter'])
    return color('well'), color('text'), color('subtle')


def mono_font(scale=.95):
    font = QFont()
    font.setFamilies(list(tokens()['font_mono']))
    font.setStyleHint(QFont.Monospace)
    font.setPixelSize(round(tokens()['font_body'] * scale))
    return font


def ink():
    return {'link': color('accent').name(), 'code_bg': css(color('tint', 44)), 'code_fg': color('text_strong').name(),
            'mono': ', '.join(f'"{family}"' for family in tokens()['font_mono']), 'muted': color('muted').name()}


class CodeEdit(QPlainTextEdit):
    """Read-only code with a line-number gutter and theme highlighting."""

    def __init__(self, text='', language='plain', parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.setTabStopDistance(4 * QFontMetrics(mono_font()).horizontalAdvance(' '))
        self.setAccessibleName('Contenido del archivo')
        self.setFont(mono_font())
        self._ink()
        self.gutter = _Gutter(self)
        self.blockCountChanged.connect(self._gutter_width)
        self.updateRequest.connect(self._gutter_scroll)
        self.highlighter = CodeHighlighter(self.document(), language)
        self.setPlainText(text)
        self._gutter_width()
        on_theme_changed(self.refresh_theme)

    def _ink(self):
        self.setStyleSheet(f'QPlainTextEdit {{background:transparent;border:0;padding:4px 0;color:{code_colors()[1].name()};}}')

    def refresh_theme(self):
        self.setFont(mono_font())
        self._ink()
        self.highlighter.refresh_theme()
        self.gutter.update()

    def gutter_width(self):
        digits = max(2, len(str(self.blockCount())))
        return 22 + QFontMetrics(self.font()).horizontalAdvance('9') * digits

    def _gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _gutter_scroll(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        area = self.contentsRect()
        self.gutter.setGeometry(QRect(area.left(), area.top(), self.gutter_width(), area.height()))

    def paint_gutter(self, painter):
        painter.setPen(code_colors()[2])
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= self.gutter.height():
            if block.isVisible() and bottom >= 0:
                painter.drawText(0, top, self.gutter.width() - 12, QFontMetrics(self.font()).height(), Qt.AlignRight, str(number + 1))
            block = block.next()
            top, bottom, number = bottom, bottom + round(self.blockBoundingRect(block).height()), number + 1


class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _event):
        painter = QPainter(self)
        self.editor.paint_gutter(painter)
        painter.setPen(color('divider'))
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())


class CodeView(QWidget):
    """Code in a rounded well with a small language chip."""

    def __init__(self, text='', language='plain', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        self.edit = CodeEdit(text, language)
        layout.addWidget(self.edit)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(code_colors()[0])
        painter.drawRoundedRect(QRectF(self.rect()), tokens()['radius_m'], tokens()['radius_m'])


# ------------------------------------------------------------------ Markdown
class _Wheel(QScrollArea):
    """Horizontal scroller that leaves vertical wheel turns to the page."""

    def wheelEvent(self, event):
        if abs(event.angleDelta().x()) > abs(event.angleDelta().y()):
            super().wheelEvent(event)
        else:
            event.ignore()


class CodeBlock(QWidget):
    message = Signal(str)

    def __init__(self, code, language_name):
        super().__init__()
        self.code, self.language_name = code, language_name
        self.setMouseTracking(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 28 if language_name else 14, 14, 10)
        language = language_for_fence(language_name)
        self.label = QLabel()
        self.label.setTextFormat(Qt.RichText)
        self.label.setFont(mono_font())
        self.label.setText(highlight_html(code, language))
        self.label.setStyleSheet(f'color:{code_colors()[1].name()};background:transparent;')
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.adjustSize()
        self.area = _Wheel()
        self.area.setFrameShape(QScrollArea.NoFrame)
        self.area.setWidget(self.label)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setFixedHeight(self.label.height() + 14)
        layout.addWidget(self.area)
        self.copy = IconButton('content_copy', 'Copiar código', self._copy, size=28, parent=self)
        self.copy.hide()
        self.copy.move(0, 0)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.code)
        self.message.emit('Código copiado')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.copy.move(self.width() - 34, 4)

    def enterEvent(self, event):
        self.copy.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.copy.hide()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(code_colors()[0])
        radius = tokens()['radius_m']
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        if self.language_name:
            painter.setFont(text_font('caption', 700))
            painter.setPen(color('subtle'))
            painter.drawText(QRect(14, 6, self.width() - 60, 18), Qt.AlignLeft | Qt.AlignVCenter, self.language_name.upper())


class Quote(QWidget):
    def __init__(self, inner):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 2, 0, 2)
        layout.addWidget(inner)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('accent', 150))
        painter.drawRoundedRect(QRectF(0, 2, 4, self.height() - 4), 2, 2)


class Marker(QWidget):
    """Bullet, number or task box of a list item."""

    def __init__(self, kind, label=''):
        super().__init__()
        self.kind, self.label = kind, label
        self.setFixedSize(28, 26)

    def paintEvent(self, _event):
        from .kit import paint_symbol
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.kind == 'bullet':
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent'))
            painter.drawEllipse(QRectF(10, 10, 6, 6))
        elif self.kind == 'number':
            painter.setFont(text_font('body', 600))
            painter.setPen(color('accent'))
            painter.drawText(QRect(0, 0, 24, 26), Qt.AlignRight | Qt.AlignVCenter, self.label)
        else:
            paint_symbol(painter, QRectF(0, 0, 24, 26), 'check_box' if self.kind == 'done' else 'check_box_outline_blank',
                         'accent' if self.kind == 'done' else 'muted', 20, filled=self.kind == 'done')


class Table(QWidget):
    def __init__(self, head, align, rows, make_label):
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(1, 1, 1, 1)
        grid.setSpacing(0)
        self.rows = len(rows) + 1
        alignment = {'left': Qt.AlignLeft, 'center': Qt.AlignHCenter, 'right': Qt.AlignRight}
        for column, cell in enumerate(head):
            label = make_label(cell, bold=True)
            label.setAlignment(alignment[align[column] if column < len(align) else 'left'] | Qt.AlignVCenter)
            label.setContentsMargins(12, 9, 12, 9)
            grid.addWidget(label, 0, column)
        for number, row in enumerate(rows, 1):
            for column in range(len(head)):
                label = make_label(row[column] if column < len(row) else '')
                label.setAlignment(alignment[align[column] if column < len(align) else 'left'] | Qt.AlignVCenter)
                label.setContentsMargins(12, 8, 12, 8)
                grid.addWidget(label, number, column)
        self.grid = grid

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_m']
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setPen(color('line'))
        painter.setBrush(color('well'))
        painter.drawRoundedRect(rect, radius, radius)
        head = self.grid.cellRect(0, 0) if hasattr(self.grid, 'cellRect') else None
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('tint', 14))
        first = self.grid.itemAtPosition(0, 0)
        if first:
            band = QRectF(rect.left(), rect.top(), rect.width(), first.geometry().height() + 1)
            path = squircle(band, 0)
            painter.setClipRect(band)
            painter.drawRoundedRect(rect, radius, radius)
            painter.setClipping(False)
        painter.setPen(color('divider'))
        for number in range(1, self.rows):
            item = self.grid.itemAtPosition(number, 0)
            if item:
                painter.drawLine(1, item.geometry().top(), self.width() - 1, item.geometry().top())


class Picture(QWidget):
    def __init__(self, source, alt, base):
        super().__init__()
        path = Path(source) if Path(source).is_absolute() else Path(base) / source
        self.pixmap = QPixmap(str(path)) if source and not source.startswith(('http:', 'https:', 'data:')) and path.is_file() else QPixmap()
        self.alt = alt
        self.setMinimumHeight(40)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if self.pixmap.isNull():
            return 44
        return min(round(self.pixmap.height() * min(1, width / self.pixmap.width())), 520)

    def sizeHint(self):
        return QSize(300, self.heightForWidth(300))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.pixmap.isNull():
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('well'))
            painter.drawRoundedRect(QRectF(self.rect()), tokens()['radius_m'], tokens()['radius_m'])
            painter.setFont(text_font('small', 500))
            painter.setPen(color('muted'))
            painter.drawText(self.rect().adjusted(14, 0, -14, 0), Qt.AlignVCenter, f'Imagen: {self.alt or "sin descripción"}')
            return
        height = self.heightForWidth(self.width())
        width = round(self.pixmap.width() * height / self.pixmap.height())
        target = QRectF(0, 0, min(width, self.width()), height)
        outline = squircle(target, 0)
        from PySide6.QtGui import QPainterPath
        shape = QPainterPath()
        shape.addRoundedRect(target, tokens()['radius_m'], tokens()['radius_m'])
        clip_pixmap(self.pixmap, shape, painter, target)


class MarkdownView(QScrollArea):
    """Rendered Markdown document; ``link`` carries clicked non-web targets."""

    link = Signal(str)
    message = Signal(str)

    def __init__(self, text='', base='', parent=None):
        super().__init__(parent)
        self.text, self.base = text, base
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAccessibleName('Documento Markdown')
        self.render_text()
        on_theme_changed(self.render_text)

    def render_text(self):
        front, body = markdown.split_front_matter(self.text)
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(22, 18, 22, 28)
        column.setSpacing(12)
        self._ink = ink()
        if front.strip():
            column.addWidget(self._front_matter(front))
        for block in markdown.parse(body):
            column.addWidget(self._block(block))
        column.addStretch()
        self.setWidget(page)

    # ---------------------------------------------------------------- blocks
    def _label(self, html, size='body', weight=400, bold=False, ink_name='text', scale=1.0):
        label = QLabel()
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setFont(text_font(size, 700 if bold else weight, scale))
        label.setText(f'<p style="margin:0;line-height:150%;">{html}</p>')
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        label.setOpenExternalLinks(False)
        label.linkActivated.connect(self._open)
        label.setStyleSheet(f'color:{color(ink_name).name()};background:transparent;')
        return label

    def _open(self, target):
        if target.startswith(('http://', 'https://', 'mailto:')):
            QDesktopServices.openUrl(QUrl(target))
        else:
            self.link.emit(target)

    def _inline_label(self, text, bold=False):
        return self._label(markdown.inline(text, self._ink), bold=bold)

    def _block(self, block):
        kind = block['t']
        if kind == 'heading':
            level = block['level']
            html = markdown.inline(block['text'], self._ink)
            if level == 1:
                holder = QWidget()
                inner = QVBoxLayout(holder)
                inner.setContentsMargins(0, 8, 0, 0)
                inner.setSpacing(8)
                inner.addWidget(self._label(html, 'title', bold=True, ink_name='text_strong'))
                rule = QWidget()
                rule.setFixedHeight(1)
                rule.setStyleSheet(f'background:{color("divider").name()};')
                inner.addWidget(rule)
                return holder
            size, scale = {2: ('heading', 1.2), 3: ('heading', 1.0)}.get(level, ('body', 1.0))
            holder = self._label(html, size, bold=True, ink_name='text_strong' if level < 4 else 'text', scale=scale)
            holder.setContentsMargins(0, 8 if level == 2 else 4, 0, 0)
            return holder
        if kind == 'para':
            return self._inline_label(block['text'])
        if kind == 'code':
            widget = CodeBlock(block['text'], block['lang'])
            widget.message.connect(self.message)
            return widget
        if kind == 'quote':
            inner = QWidget()
            layout = QVBoxLayout(inner)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            for child in block['children']:
                layout.addWidget(self._block(child))
            return Quote(inner)
        if kind == 'list':
            holder = QWidget()
            layout = QVBoxLayout(holder)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            for number, item in enumerate(block['items']):
                row = QWidget()
                line = QHBoxLayout(row)
                line.setContentsMargins(0, 0, 0, 0)
                line.setSpacing(0)
                if item['task'] is not None:
                    marker = Marker('done' if item['task'] else 'todo')
                elif block['ordered']:
                    marker = Marker('number', f"{block['start'] + number}.")
                else:
                    marker = Marker('bullet')
                line.addWidget(marker, 0, Qt.AlignTop)
                content = QWidget()
                inner = QVBoxLayout(content)
                inner.setContentsMargins(0, 0, 0, 0)
                inner.setSpacing(6)
                for child in item['children']:
                    inner.addWidget(self._block(child))
                line.addWidget(content, 1)
                layout.addWidget(row)
            return holder
        if kind == 'table':
            return Table(block['head'], block['align'], block['rows'],
                         lambda cell, bold=False: self._inline_label(cell, bold))
        if kind == 'rule':
            rule = QWidget()
            rule.setFixedHeight(1)
            rule.setStyleSheet(f'background:{color("divider").name()};')
            return rule
        return Picture(block['src'], block['alt'], self.base)

    def _front_matter(self, text):
        label = QLabel(text.strip())
        label.setFont(mono_font(.85))
        label.setWordWrap(True)
        label.setContentsMargins(14, 10, 14, 10)
        label.setStyleSheet(f'color:{color("muted").name()};background:{css(color("tint", 14))};border-radius:{tokens()["radius_m"]}px;')
        return label
