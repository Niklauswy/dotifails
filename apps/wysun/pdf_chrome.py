"""Reader pieces built on the shared kit: control groups, zoom, view mode, page indicator,
the selection's annotation bar, the empty state and the note dialog.

Colours, type, shape and motion are the theme's (wysun_core.qt_theme, wysun_core.ui); nothing here
paints with a colour of its own except the annotation inks, which are written into the PDF.
"""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIntValidator, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QDialog, QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from wysun_core.qt_theme import color, tokens
from wysun_core.ui.shapes import cookie
from wysun_core.ui.style import apply_kit_style, metric, paint_symbol, text_font
from wysun_core.ui.widgets import ElidedLabel, IconButton, PillButton, StateLayer

CONTROL = 38          # top-bar controls, as in Files
PRESETS = (.5, .75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)
# theme-exception-begin: muestras de color del usuario; se escriben en el PDF y deben leerse en cualquier lector
MARKERS = (('Amarillo', (1.0, .86, .2)), ('Verde', (.47, .86, .45)), ('Rosa', (1.0, .5, .72)),
           ('Azul', (.42, .7, 1.0)))
# theme-exception-end


def ink_colours():
    """(name, QColor): the theme accent first, then classic highlighter colours."""
    return [('Acento', color('accent'))] + [(name, QColor.fromRgbF(*rgb)) for name, rgb in MARKERS]


class ToolGroup(QWidget):
    """A pill well that holds a few related controls."""

    def __init__(self, *widgets, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        inset = metric('space_xs') // 2
        row.setContentsMargins(inset, inset, inset, inset)
        row.setSpacing(0)
        for widget in widgets:
            row.addWidget(widget)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('well'))
        rect = QRectF(self.rect())
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)


class TextButton(QAbstractButton):
    """Flat label-only button (the zoom percentage)."""

    def __init__(self, text, label, parent=None):
        super().__init__(parent)
        self.layer = StateLayer(self)
        self.setText(text)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFont(text_font('small', 600))
        self.setFixedHeight(CONTROL - 4)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance('8888 %') + metric('space_m'), self.height())

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        if self.layer.amount:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', round(18 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        if self.hasFocus():
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(color('text' if self.isEnabled() else 'disabled'))
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())


class ZoomControl(ToolGroup):
    """− / percentage (menu: fit width, fit page, presets) / +."""

    zoom_in = Signal()
    zoom_out = Signal()
    fit = Signal(str)
    percent = Signal(float)

    def __init__(self, parent=None):
        self.minus = IconButton('remove', 'Alejar · Ctrl −', lambda: self.zoom_out.emit(), size=CONTROL - 4)
        self.label = TextButton('100 %', 'Zoom')
        self.plus = IconButton('add', 'Acercar · Ctrl +', lambda: self.zoom_in.emit(), size=CONTROL - 4)
        super().__init__(self.minus, self.label, self.plus, parent=parent)
        self.label.clicked.connect(self.open_menu)

    def set_zoom(self, value, mode):
        self.label.setText(f'{round(value * 100)} %')
        described = {'width': 'ajustado al ancho', 'page': 'página completa'}.get(mode, 'personalizado')
        self.label.setAccessibleName(f'Zoom {round(value * 100)} %, {described}')
        self.label.setToolTip(f'Zoom · {described}')

    def choose(self, value):
        if isinstance(value, str):
            self.fit.emit(value)
        else:
            self.percent.emit(value)

    def open_menu(self):
        menu = QMenu(self)
        menu.addAction('Ajustar al ancho · Ctrl 0', lambda: self.choose('width'))
        menu.addAction('Ajustar a la página · Ctrl 9', lambda: self.choose('page'))
        menu.addSeparator()
        for value in PRESETS:
            menu.addAction(f'{round(value * 100)} %', lambda v=value: self.choose(v))
        menu.exec(self.label.mapToGlobal(self.label.rect().bottomLeft()))


class ViewModeSwitch(ToolGroup):
    """One continuous column or two pages side by side."""

    changed = Signal(str)

    def __init__(self, parent=None):
        self.buttons = {
            'single': IconButton('view_agenda', 'Una página, continua', lambda: self._pick('single'),
                                 variant='tonal', size=CONTROL - 4, checkable=True),
            'spread': IconButton('auto_stories', 'Dos páginas · Ctrl 2', lambda: self._pick('spread'),
                                 variant='tonal', size=CONTROL - 4, checkable=True)}
        super().__init__(*self.buttons.values(), parent=parent)
        self.set_mode('single')

    def _pick(self, mode):
        self.set_mode(mode)
        self.changed.emit(mode)

    def set_mode(self, mode):
        for name, button in self.buttons.items():
            button.setChecked(name == mode)


class PageIndicator(QWidget):
    """Floating "3 / 40" pill over the document; clicking it (or Ctrl+G) turns it into a page field."""

    jump = Signal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.page, self.total = 0, 0
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setFont(text_font('small', 600))
        self.setFixedHeight(CONTROL - 2)
        self.editor = QLineEdit(self)
        self.editor.setAlignment(Qt.AlignCenter)
        self.editor.setAccessibleName('Ir a la página')
        self.editor.setValidator(QIntValidator(1, 999999, self.editor))
        self.editor.returnPressed.connect(self._commit)
        self.editor.editingFinished.connect(self._finish)
        self.editor.hide()
        self.setToolTip('Ir a la página · Ctrl G')
        self.hide()

    def set_page(self, page, total):
        self.page, self.total = page, total
        self.setAccessibleName(f'Página {page + 1} de {total}')
        self.place()
        self.update()

    def label(self):
        return f'{self.page + 1} / {self.total}'

    def place(self):
        parent = self.parentWidget()
        width = self.fontMetrics().horizontalAdvance(f'{self.total} / {self.total}') + metric('space_xl') * 2
        self.setGeometry((parent.width() - width) // 2, parent.height() - self.height() - metric('space_l'),
                         width, self.height())
        self.editor.setGeometry(self.rect().adjusted(metric('space_s'), 4, -metric('space_s'), -4))
        self.raise_()

    def start_edit(self):
        if not self.total:
            return
        self.editor.setText(str(self.page + 1))
        self.editor.show()
        self.editor.selectAll()
        self.editor.setFocus(Qt.ShortcutFocusReason)

    def _commit(self):
        if self.editor.text():
            self.jump.emit(max(1, min(self.total, int(self.editor.text()))) - 1)
        self._finish()

    def _finish(self):
        self.editor.hide()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_edit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.start_edit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        radius = rect.height() / 2
        painter.setPen(QPen(color('focus') if self.hasFocus() else color('line'), tokens()['border']))
        painter.setBrush(color('surface_raised'))
        painter.drawRoundedRect(rect, radius, radius)
        if not self.editor.isVisible():
            painter.setPen(color('text'))
            painter.setFont(self.font())
            painter.drawText(rect, Qt.AlignCenter, self.label())


class InkButton(QAbstractButton):
    """A round swatch of the current annotation colour."""

    def __init__(self, ink, parent=None):
        super().__init__(parent)
        self.ink = ink
        self.setAccessibleName('Color de anotación')
        self.setToolTip('Color de anotación')
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(CONTROL - 4, CONTROL - 4)

    def set_ink(self, ink):
        self.ink = ink
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        swatch = QRectF(self.rect()).adjusted(9, 9, -9, -9)
        painter.setPen(QPen(color('focus') if self.hasFocus() else color('line'), 2))
        painter.setBrush(self.ink)
        painter.drawEllipse(swatch)


class SelectionBar(QWidget):
    """Floating capsule over a text selection: highlight, underline, copy and ink."""

    action = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        row = QHBoxLayout(self)
        inset = metric('space_xs')
        row.setContentsMargins(inset, inset, inset, inset)
        row.setSpacing(0)
        size = CONTROL - 4
        self.buttons = {
            'highlight': IconButton('ink_highlighter', 'Resaltar · Ctrl H', lambda: self.action.emit('highlight'), size=size),
            'underline': IconButton('format_underlined', 'Subrayar · Ctrl U', lambda: self.action.emit('underline'), size=size),
            'copy': IconButton('content_copy', 'Copiar · Ctrl C', lambda: self.action.emit('copy'), size=size)}
        self.ink = InkButton(ink_colours()[0][1])
        self.ink.clicked.connect(lambda: self.action.emit('ink'))
        self.buttons['ink'] = self.ink
        for button in self.buttons.values():
            row.addWidget(button)
        self.setAccessibleName('Acciones de la selección')
        self.hide()

    def set_editable(self, editable):
        for name in ('highlight', 'underline', 'ink'):
            self.buttons[name].setVisible(editable)
        self.adjustSize()

    def place(self, rect):
        """Centre above ``rect`` (parent coordinates); below it when there is no room above."""
        self.adjustSize()
        parent = self.parentWidget()
        gap = metric('space_s')
        x = max(gap, min(parent.width() - self.width() - gap, rect.center().x() - self.width() // 2))
        y = rect.top() - self.height() - gap
        if y < gap:
            y = rect.bottom() + gap
        self.move(x, max(gap, min(parent.height() - self.height() - gap, y)))
        self.raise_()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        radius = rect.height() / 2
        painter.setPen(QPen(color('line'), tokens()['border']))
        painter.setBrush(color('surface_raised'))
        painter.drawRoundedRect(rect, radius, radius)


def ink_menu(parent, choose, other):
    """Menu of annotation colours: ``choose(QColor)`` for a swatch, ``other()`` for the picker."""
    from PySide6.QtGui import QIcon, QPixmap
    menu = QMenu(parent)
    for name, ink in ink_colours():
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(color('line'), 1))
        painter.setBrush(ink)
        painter.drawEllipse(QRectF(1, 1, 14, 14))
        painter.end()
        menu.addAction(QIcon(pixmap), name, lambda value=ink: choose(value))
    menu.addSeparator()
    menu.addAction('Otro color…', other)
    return menu


class Emblem(QWidget):
    """The reader's identity: a Material cookie with a book."""

    def __init__(self, size=72, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAccessibleName('Wysun PDF')

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('accent'))
        painter.drawPath(cookie(QRectF(self.rect()).adjusted(1, 1, -1, -1), 9))
        paint_symbol(painter, self.rect(), 'menu_book', 'on_accent', self.width() * .42, filled=True)


class EmptyState(QWidget):
    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setSpacing(metric('space_m'))
        column.addStretch(3)
        column.addWidget(Emblem(), 0, Qt.AlignHCenter)
        column.addSpacing(metric('space_m'))
        title = QLabel('Abre un PDF')
        title.setFont(text_font('title', 600))
        body = QLabel('Lee de corrido y marca lo importante.\nTus notas se guardan dentro del propio PDF.')
        body.setObjectName('muted')
        for label in (title, body):
            label.setAlignment(Qt.AlignHCenter)
            column.addWidget(label, 0, Qt.AlignHCenter)
        column.addSpacing(metric('space_s'))
        self.button = PillButton('folder_open', 'Abrir un PDF', lambda: self.open_requested.emit(), height=44)
        column.addWidget(self.button, 0, Qt.AlignHCenter)
        hint = QLabel('o arrastra un archivo aquí · Ctrl O')
        hint.setObjectName('muted')
        hint.setAlignment(Qt.AlignHCenter)
        column.addWidget(hint)
        column.addStretch(4)


class NoteDialog(QDialog):
    def __init__(self, parent=None, text='', title='Añadir una nota'):
        super().__init__(parent)
        self.setWindowTitle(title)
        apply_kit_style(self)
        from wysun_core.qt_theme import extend_style
        extend_style(self, 'QDialog {background:@surface_raised;} QPlainTextEdit {background:@well;'
                           'border:@border solid @line;border-radius:@radius_control;padding:@space_s;'
                           'selection-background-color:@text_selection;}'
                           'QPlainTextEdit:focus {border:@focus_width solid @focus_input;}')
        self.setMinimumWidth(440)
        column = QVBoxLayout(self)
        pad = metric('space_xl')
        column.setContentsMargins(pad, pad, pad, pad)
        column.setSpacing(metric('space_m'))
        heading = ElidedLabel(title, 'heading', 650)
        column.addWidget(heading)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName('Texto de la nota')
        self.editor.setPlainText(text)
        self.editor.setPlaceholderText('Escribe aquí…')
        self.editor.setMinimumHeight(140)
        column.addWidget(self.editor)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(PillButton('close', 'Cancelar', self.reject, variant='tonal', height=40))
        self.save = PillButton('check', 'Guardar nota', self.accept, height=40)
        buttons.addWidget(self.save)
        column.addLayout(buttons)
        self.editor.textChanged.connect(lambda: self.save.setEnabled(bool(self.editor.toPlainText().strip())))
        self.save.setEnabled(bool(text.strip()))
        self.editor.setFocus()

