"""The reader's foldable side panel: Páginas, Índice, Notas and Resultados, painted from the kit."""
from collections import OrderedDict

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QListView, QListWidget, QListWidgetItem, QStackedWidget,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from wysun_core.qt_theme import color, tokens
from wysun_core.ui.style import metric, text_font
from wysun_core.ui.widgets import ElidedLabel, IconButton, PillButton

WIDTH = 244
THUMBNAILS = 48              # thumbnails kept in memory
TABS = (('grid_view', 'Páginas'), ('toc', 'Índice'), ('sticky_note_2', 'Notas'), ('search', 'Resultados'))
SECONDARY = Qt.UserRole + 2  # small muted line above the row text
TERM = Qt.UserRole + 3       # search term to embolden in the row text
KINDS = {'Highlight': 'Resaltado', 'Underline': 'Subrayado', 'Text': 'Nota', 'StrikeOut': 'Tachado',
         'FreeText': 'Texto', 'Ink': 'Trazo'}


class PageModel(QAbstractListModel):
    """Page numbers with the thumbnails loaded so far (least recently loaded dropped first)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pages, self.images, self.current = 0, OrderedDict(), 0

    def reset(self, pages):
        self.beginResetModel()
        self.pages, self.current = pages, 0
        self.images.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.pages

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return str(index.row() + 1)
        if role == Qt.UserRole:
            return self.images.get(index.row())
        if role == Qt.AccessibleTextRole:
            return f'Página {index.row() + 1}'
        return None

    def put(self, page, image):
        self.images[page] = image
        self.images.move_to_end(page)
        while len(self.images) > THUMBNAILS:
            self.images.popitem(last=False)
        index = self.index(page, 0)
        self.dataChanged.emit(index, index)

    def forget(self, page):
        self.images.pop(page, None)


class ThumbnailDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(104, 168)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cell = QRectF(option.rect).adjusted(4, 4, -4, -4)
        current = index.row() == index.model().current
        label = QRectF(cell.left(), cell.bottom() - 22, cell.width(), 22)
        area = cell.adjusted(6, 4, -6, -26)
        image = index.data(Qt.UserRole)
        if image is not None and not image.isNull():
            size = image.size().scaled(int(area.width()), int(area.height()), Qt.KeepAspectRatio)
            area = QRectF(area.center().x() - size.width() / 2, area.center().y() - size.height() / 2,
                          size.width(), size.height())
            painter.drawImage(area, image)
        else:
            area = QRectF(area.center().x() - area.width() * .36, area.top(), area.width() * .72, area.height())
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('well'))
            painter.drawRect(area)
        radius = tokens()['corner_xs']
        if current:
            painter.setPen(QPen(color('accent'), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(area.adjusted(-3, -3, 3, 3), radius, radius)
        elif option.state & QStyle.State_MouseOver:
            painter.setPen(QPen(color('line'), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(area.adjusted(-2, -2, 2, 2), radius, radius)
        if option.state & QStyle.State_HasFocus:
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.drawRoundedRect(cell, radius * 2, radius * 2)
        painter.setPen(color('accent' if current else 'muted'))
        painter.setFont(text_font('small', 700 if current else 500))
        painter.drawText(label, Qt.AlignCenter, index.data())
        painter.restore()


class RowDelegate(QStyledItemDelegate):
    """Rounded list row with an optional muted line above and an emboldened search term."""

    def sizeHint(self, option, index):
        return QSize(180, 56 if index.data(SECONDARY) else 36)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 1, 0, -1)
        radius = tokens()['radius_m']
        selected = bool(option.state & QStyle.State_Selected)
        if selected or option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('row_selected' if selected else 'row_hover'))
            painter.drawRoundedRect(rect, radius, radius)
        if option.state & QStyle.State_HasFocus:
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
        inner = rect.adjusted(metric('space_m'), 0, -metric('space_m'), 0)
        secondary = index.data(SECONDARY)
        if secondary:
            painter.setFont(text_font('caption', 600))
            painter.setPen(color('muted'))
            top = QRectF(inner.left(), inner.top() + 6, inner.width(), 18)
            painter.drawText(top, Qt.AlignLeft | Qt.AlignVCenter, secondary)
            inner = QRectF(inner.left(), top.bottom(), inner.width(), inner.bottom() - top.bottom() - 4)
        self._text(painter, inner, str(index.data() or ''), index.data(TERM), selected)
        painter.restore()

    def _text(self, painter, rect, text, term, selected):
        regular, bold = text_font('body', 600 if selected else 400), text_font('body', 700)
        painter.setPen(color('text'))
        at = text.lower().find(term.lower()) if term else -1
        if at < 0:
            painter.setFont(regular)
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(text, Qt.ElideRight, int(rect.width())))
            return
        x, right = rect.left(), rect.right()
        for part, font in ((text[:at], regular), (text[at:at + len(term)], bold), (text[at + len(term):], regular)):
            painter.setFont(font)
            metrics = painter.fontMetrics()
            shown = metrics.elidedText(part, Qt.ElideRight, int(right - x))
            painter.setPen(color('accent' if font is bold else 'text'))
            painter.drawText(QRectF(x, rect.top(), right - x, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, shown)
            x += metrics.horizontalAdvance(shown)
            if shown != part or x >= right:
                break


def _list():
    widget = QListWidget()
    widget.setFrameShape(QFrame.NoFrame)
    widget.setMouseTracking(True)
    widget.setItemDelegate(RowDelegate(widget))
    widget.setSpacing(1)
    widget.setVerticalScrollMode(QListWidget.ScrollPerPixel)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return widget


class Sidebar(QWidget):
    page_requested = Signal(int)          # thumbnail or outline entry
    result_requested = Signal(int)        # index in the results list
    note_selected = Signal(dict)
    note_activated = Signal(dict)         # edit it
    delete_requested = Signal(dict)
    thumbnails_wanted = Signal()
    tab_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(WIDTH)
        column = QVBoxLayout(self)
        column.setContentsMargins(metric('space_xs'), 0, 0, 0)
        column.setSpacing(metric('space_s'))
        tabs = QHBoxLayout()
        tabs.setSpacing(metric('space_xs'))
        self.tabs = []
        for index, (symbol, label) in enumerate(TABS):
            button = IconButton(symbol, label, lambda i=index: self.set_tab(i), variant='tonal', size=40, checkable=True)
            button.outline = symbol == 'toc'
            tabs.addWidget(button)
            self.tabs.append(button)
        tabs.addStretch()
        column.addLayout(tabs)
        self.heading = ElidedLabel('Páginas', 'heading', 650)
        self.meta = ElidedLabel('', 'small', 450, tint='muted')
        heading = QVBoxLayout()
        heading.setContentsMargins(metric('space_s'), metric('space_s'), 0, 0)
        heading.setSpacing(2)
        heading.addWidget(self.heading)
        heading.addWidget(self.meta)
        column.addLayout(heading)
        self.stack = QStackedWidget()
        column.addWidget(self.stack, 1)

        self.pages = QListView()
        self.pages.setAccessibleName('Miniaturas de las páginas')
        self.pages.setViewMode(QListView.IconMode)
        self.pages.setResizeMode(QListView.Adjust)
        self.pages.setMovement(QListView.Static)
        self.pages.setUniformItemSizes(True)
        self.pages.setGridSize(QSize(112, 172))
        self.pages.setFrameShape(QFrame.NoFrame)
        self.pages.setMouseTracking(True)
        self.pages.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.pages.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pages.setItemDelegate(ThumbnailDelegate(self.pages))
        self.page_model = PageModel(self.pages)
        self.pages.setModel(self.page_model)
        self.pages.clicked.connect(lambda index: self.page_requested.emit(index.row()))
        self.pages.activated.connect(lambda index: self.page_requested.emit(index.row()))
        self.pages.verticalScrollBar().valueChanged.connect(lambda _: self.thumbnails_wanted.emit())
        self.stack.addWidget(self.pages)

        self.outline = _list()
        self.outline.setAccessibleName('Índice del documento')
        self.outline.itemClicked.connect(self._outline)
        self.outline.itemActivated.connect(self._outline)
        self.stack.addWidget(self.outline)

        notes = QWidget()
        notes_column = QVBoxLayout(notes)
        notes_column.setContentsMargins(0, 0, 0, 0)
        self.notes = _list()
        self.notes.setAccessibleName('Anotaciones del documento')
        self.notes.itemClicked.connect(lambda item: self.note_selected.emit(item.data(Qt.UserRole)))
        self.notes.itemActivated.connect(lambda item: self.note_activated.emit(item.data(Qt.UserRole)))
        self.notes.currentItemChanged.connect(lambda *_: self._sync_delete())
        notes_column.addWidget(self.notes, 1)
        self.delete_button = PillButton('delete', 'Eliminar', self._delete, variant='tonal', height=40)
        self.delete_button.setToolTip('Eliminar la anotación · Supr')
        notes_column.addWidget(self.delete_button)
        self.stack.addWidget(notes)

        self.results = _list()
        self.results.setAccessibleName('Resultados de la búsqueda')
        self.results.itemClicked.connect(lambda item: self.result_requested.emit(self.results.row(item)))
        self.results.itemActivated.connect(lambda item: self.result_requested.emit(self.results.row(item)))
        self.stack.addWidget(self.results)
        self.editable = False
        self.results_meta = 'Busca con Ctrl F'
        self.set_tab(0)

    # ----------------------------------------------------------------- tabs
    def set_tab(self, index):
        self.stack.setCurrentIndex(index)
        for number, button in enumerate(self.tabs):
            button.setChecked(number == index)
        self.heading.setText(TABS[index][1])
        self._meta()
        self.tab_changed.emit(index)
        if index == 0:
            self.thumbnails_wanted.emit()

    def current_tab(self):
        return self.stack.currentIndex()

    def _meta(self):
        index = self.current_tab()
        if index == 0:
            text = f'{self.page_model.pages} páginas' if self.page_model.pages else ''
        elif index == 1:
            text = f'{self.outline.count()} entradas' if self.outline.isEnabled() else 'Sin índice'
        elif index == 2:
            count = sum(1 for row in range(self.notes.count()) if self.notes.item(row).data(Qt.UserRole))
            text = f'{count} en el documento' if count else 'Ninguna todavía'
        else:
            text = self.results_meta
        self.meta.setText(text)

    # ---------------------------------------------------------------- pages
    def reset(self, pages, editable):
        self.editable = editable
        self.page_model.reset(pages)
        self.outline.clear()
        self.notes.clear()
        self.results.clear()
        self.results_meta = 'Busca con Ctrl F'
        self._sync_delete()
        self._meta()

    def set_current_page(self, page):
        self.page_model.current = page
        index = self.page_model.index(page, 0)
        if index.isValid():
            self.pages.scrollTo(index)
        self.pages.viewport().update()

    def visible_thumbnails(self):
        """Rows whose thumbnails are on screen, top first, plus one row of margin."""
        view = self.pages
        if not view.isVisible() or not self.page_model.pages:
            return []
        first = view.indexAt(view.viewport().rect().topLeft())
        start = max(0, first.row() if first.isValid() else 0)
        per_row = max(1, view.viewport().width() // view.gridSize().width())
        count = (view.viewport().height() // view.gridSize().height() + 2) * per_row
        return list(range(start, min(self.page_model.pages, start + count)))

    # -------------------------------------------------------------- outline
    def set_outline(self, outline):
        self.outline.clear()
        for entry in outline:
            level, title, page = entry[:3]
            item = QListWidgetItem('    ' * min(level - 1, 5) + title)
            item.setData(Qt.UserRole, page - 1)
            item.setToolTip(title)
            self.outline.addItem(item)
        self.outline.setEnabled(bool(outline))
        if not outline:
            item = QListWidgetItem('Este PDF no tiene índice')
            item.setFlags(Qt.NoItemFlags)
            self.outline.addItem(item)
        self._meta()

    def _outline(self, item):
        page = item.data(Qt.UserRole)
        if page is not None and page >= 0:
            self.page_requested.emit(page)

    # ---------------------------------------------------------------- notes
    def set_notes(self, items):
        current = self.notes.currentItem().data(Qt.UserRole) if self.notes.currentItem() else None
        self.notes.clear()
        for note in items:
            kind = KINDS.get(note['type'], note['type'])
            item = QListWidgetItem(note['text'].strip().replace('\n', ' ') or kind)
            item.setData(SECONDARY, f'PÁGINA {note["page"] + 1} · {kind.upper()}')
            item.setData(Qt.UserRole, note)
            item.setToolTip(note['text'])
            self.notes.addItem(item)
            if current and (current['page'], current['xref']) == (note['page'], note['xref']):
                self.notes.setCurrentItem(item)
        if not items:
            item = QListWidgetItem('Selecciona texto para resaltar o coloca una nota')
            item.setFlags(Qt.NoItemFlags)
            self.notes.addItem(item)
        self._sync_delete()
        self._meta()

    def selected_note(self):
        item = self.notes.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _sync_delete(self):
        self.delete_button.setEnabled(self.editable and self.selected_note() is not None)

    def _delete(self):
        note = self.selected_note()
        if note is not None and self.delete_button.isEnabled():
            self.delete_requested.emit(note)

    # -------------------------------------------------------------- results
    def set_results(self, term, rows, status=''):
        """``rows``: (page, context) per match, in document order."""
        self.results.clear()
        self.add_results(term, rows, status or f'{len(rows)} coincidencias')

    def add_results(self, term, rows, status):
        for page, context in rows:
            item = QListWidgetItem(context or f'Página {page + 1}')
            item.setData(SECONDARY, f'PÁGINA {page + 1}')
            item.setData(TERM, term)
            self.results.addItem(item)
        self.results_meta = status
        self._meta()

    def select_result(self, index):
        if 0 <= index < self.results.count():
            self.results.setCurrentRow(index)
            self.results.scrollToItem(self.results.item(index))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self.current_tab() == 2:
            self._delete()
        else:
            super().keyPressEvent(event)

