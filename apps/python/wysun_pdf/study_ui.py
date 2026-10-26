"""Study-specific compositions on the shared Material You kit, not a second theme."""
import json
import sqlite3
from wysun_pdf.study import StudyConflict

from PySide6.QtCore import Qt, QRectF, Signal, QVariantAnimation, QPropertyAnimation, QParallelAnimationGroup, QPoint
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                               QAbstractButton, QPlainTextEdit, QMenu, QMessageBox, QGraphicsOpacityEffect,
                               QDialog, QCheckBox)

from wysun_core.qt_theme import color, tokens, easing, extend_style
from wysun_core.ui.panels import Panel, SearchField
from wysun_core.ui.widgets import IconButton, PillButton, StateLayer
from wysun_core.ui.style import metric, text_font, paint_symbol, apply_kit_style
from wysun_core.ui.shapes import cookie
from wysun_core.ui.motion import reveal_content, reduced_motion

STORAGE_ERRORS = (OSError, ValueError, sqlite3.Error)


def control_height():
    return metric('spacing.extraExtraLarge')


def label(text, role='body.medium', tint='text'):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(True)
    widget.setFont(text_font(role))
    extend_style(widget, f'QLabel {{color:@{tint};}}')
    return widget


def layout(parent, horizontal=False, padding='padding.largeIncreased'):
    result = QHBoxLayout(parent) if horizontal else QVBoxLayout(parent)
    pad = metric(padding)
    result.setContentsMargins(pad, pad, pad, pad)
    result.setSpacing(metric('spacing.medium'))
    return result


def reveal(widget):
    reveal_content(widget, metric('anim.durations.expressiveDefaultEffects'))
    if hasattr(widget, '_reveal_animation'):
        widget._reveal_animation.setEasingCurve(easing('anim.curves.expressiveDefaultEffects'))


def navigate(stack, target):
    """A short outgoing snapshot leaves the layout stable during a page transition.

    One viewport-sized pixmap, released on completion/interruption. PDF rasters are
    never rendered on animation ticks. Input always reaches the incoming page.
    """
    host, old = stack.parentWidget(), stack.currentWidget()
    previous = getattr(host, '_study_transition', None)
    if previous:
        previous[0].stop()
        previous[1].hide()
        previous[1].deleteLater()
        previous[0].deleteLater()
        host._study_transition = None
    if old is target or not old or not host.isVisible() or reduced_motion(host.window()):
        stack.setCurrentWidget(target)
        return
    pixmap, geometry = old.grab(), old.geometry()
    stack.setCurrentWidget(target)
    overlay = QLabel(host)
    overlay.setPixmap(pixmap)
    overlay.setGeometry(geometry)
    overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
    effect = QGraphicsOpacityEffect(overlay)
    overlay.setGraphicsEffect(effect)
    group = QParallelAnimationGroup(host)
    fade = QPropertyAnimation(effect, b'opacity', group)
    fade.setStartValue(1.)
    fade.setEndValue(0.)
    fade.setDuration(metric('anim.durations.expressiveDefaultEffects'))
    fade.setEasingCurve(easing('anim.curves.expressiveDefaultEffects'))
    move = QPropertyAnimation(overlay, b'pos', group)
    move.setStartValue(geometry.topLeft())
    move.setEndValue(geometry.topLeft() + QPoint(0, -metric('anim.lift')))
    move.setDuration(metric('anim.durations.expressiveFastSpatial'))
    move.setEasingCurve(easing('anim.curves.emphasizedAccel'))
    group.addAnimation(fade)
    group.addAnimation(move)
    host._study_transition = (group, overlay)
    def finished():
        overlay.hide()
        overlay.deleteLater()
        group.deleteLater()
        if getattr(host, '_study_transition', None) == (group, overlay):
            host._study_transition = None
    group.finished.connect(finished)
    overlay.show()
    overlay.raise_()
    group.start()


class ReadingArt(QWidget):
    """Finite, hover-driven spatial motion; no timer runs while the reader is idle."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(metric('spacing.extraExtraLarge', 4), metric('spacing.extraExtraLarge', 4))
        self.phase = 0.
        self.motion = QVariantAnimation(self)
        self.motion.setEasingCurve(easing('anim.curves.expressiveDefaultSpatial'))
        self.motion.valueChanged.connect(self.advance)
        self.setAccessibleName('Ilustración de lectura')

    def advance(self, value):
        self.phase = float(value)
        self.update()

    def animate(self, target):
        self.motion.stop()
        if reduced_motion(self.window()):
            self.advance(target)
            return
        self.motion.setDuration(metric('anim.durations.expressiveDefaultSpatial'))
        self.motion.setStartValue(self.phase)
        self.motion.setEndValue(target)
        self.motion.start()

    def enterEvent(self, event):
        self.animate(1.)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate(0.)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        inset = metric('spacing.medium')
        box = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        p.setPen(Qt.NoPen)
        p.setBrush(color('accent'))
        p.drawPath(cookie(box, 9, self.phase * 12))
        p.translate(box.center())
        p.rotate(-8 + self.phase * 8)
        side = box.width() * .6
        paint_symbol(p, QRectF(-side/2, -side/2, side, side), 'auto_stories', 'on_accent', side)


class BookRow(QAbstractButton):
    def __init__(self, book, open_book, forget):
        super().__init__()
        self.book, self.forget = book, forget
        self.layer = StateLayer(self)
        self.setMinimumHeight(metric('spacing.extraExtraLarge', 2))
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(f'{book["title"]}, página {book["page"] + 1} de {book["pages"]}')
        self.setToolTip(book['path'])
        self.clicked.connect(lambda: open_book(book['path']))

    def enterEvent(self, event):
        self.layer.to(1.)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.)
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('Quitar de recientes (conservar notas)', lambda: self.forget(self.book['id']))
        menu.exec(event.globalPos())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pad, gap = metric('padding.large'), metric('spacing.large')
        box = QRectF(self.rect()).adjusted(0, 0, 0, -metric('spacing.extraSmall'))
        p.setPen(Qt.NoPen)
        p.setBrush(color('hover' if self.isDown() else 'surface'))
        radius = metric('rounding.large')
        p.drawRoundedRect(box, radius, radius)
        if self.layer.amount:
            p.setOpacity(self.layer.amount)
            p.setBrush(color('hover'))
            p.drawRoundedRect(box, radius, radius)
            p.setOpacity(1)
        if self.hasFocus():
            p.setPen(QPen(color('focus'), tokens()['border.focus']))
            p.setBrush(Qt.NoBrush)
            border = metric('border.focus')
            p.drawRoundedRect(box.adjusted(border, border, -border, -border), radius, radius)
        cover = QRectF(pad, pad, metric('spacing.extraExtraLarge'), box.height()-2*pad)
        p.setPen(Qt.NoPen)
        p.setBrush(color('fill'))
        p.drawRoundedRect(cover, metric('rounding.small'), metric('rounding.small'))
        paint_symbol(p, cover, 'menu_book', 'accent', metric('icon.size'))
        left = cover.right() + gap
        right = metric('spacing.extraExtraLarge', 2)
        p.setFont(text_font('title.medium'))
        p.setPen(color('text'))
        title_box = QRectF(left, pad, max(0, box.width()-left-right), box.height()/2-pad)
        p.drawText(title_box, Qt.AlignVCenter, p.fontMetrics().elidedText(self.book['title'], Qt.ElideRight, int(title_box.width())))
        p.setFont(text_font('body.small'))
        p.setPen(color('muted'))
        details = f'Página {self.book["page"]+1} de {self.book["pages"]}  ·  {self.book["notes"]} notas'
        p.drawText(QRectF(left, box.height()/2, title_box.width(), box.height()/2-pad), Qt.AlignVCenter, details)
        paint_symbol(p, QRectF(box.width()-right, 0, right, box.height()), 'arrow_forward', 'accent', metric('icon.size'))


class LibraryView(QWidget):
    open_requested = Signal(str)
    choose_requested = Signal()
    settings_requested = Signal()
    message = Signal(str)

    def __init__(self, store):
        super().__init__()
        self.store, self.books = store, []
        outer = layout(self, padding='padding.extraLarge')
        top = QHBoxLayout()
        top.addWidget(label('Wysun PDF', 'title.medium'))
        top.addStretch()
        self.search = SearchField('Buscar en biblioteca')
        self.search.setPlaceholderText('Buscar en tu biblioteca')
        self.search.setToolTip('Buscar por título')
        self.search.setMaximumWidth(metric('spacing.extraExtraLarge', 8))
        self.search.textChanged.connect(self.filter)
        top.addWidget(self.search)
        top.addWidget(IconButton('settings', 'Ajustes', self.settings_requested.emit, size=control_height()))
        top.addWidget(IconButton('close', 'Cerrar', lambda: self.window().close(), size=control_height()))
        outer.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        body = layout(content, padding='padding.extraSmall')
        body.setSpacing(metric('spacing.extraLarge'))
        body.addWidget(label('TU ESPACIO DE ESTUDIO', 'label.small', 'accent'))
        self.heading = label('Una lectura.\nMuchas ideas.', 'headline.large')
        body.addWidget(self.heading)
        self.hero = Panel()
        hero = layout(self.hero, True, 'padding.extraLarge')
        copy = QVBoxLayout()
        copy.setSpacing(metric('spacing.medium'))
        self.eyebrow = label('EMPIEZA POR LO QUE TE DA CURIOSIDAD', 'label.small', 'accent')
        self.book_title = label('Tu próximo capítulo empieza aquí', 'title.large')
        self.meta = label('Lee con calma. Conecta una idea con otra.\nGuarda tus reflexiones junto al pasaje.', 'body.medium', 'muted')
        copy.addWidget(self.eyebrow)
        copy.addWidget(self.book_title)
        copy.addWidget(self.meta)
        copy.addStretch()
        self.continue_button = PillButton('folder_open', 'Abrir mi primer PDF', self.continue_reading, height=control_height())
        copy.addWidget(self.continue_button, 0, Qt.AlignLeft)
        hero.addLayout(copy, 1)
        self.art = ReadingArt()
        hero.addWidget(self.art)
        body.addWidget(self.hero)
        section = QHBoxLayout()
        section.addWidget(label('Tu biblioteca', 'title.large'))
        section.addStretch()
        self.open_button = PillButton('add', 'Abrir PDF', self.choose_requested.emit, 'tonal', control_height())
        section.addWidget(self.open_button)
        body.addLayout(section)
        self.status = label('Los documentos que abras aparecerán aquí. Tus originales permanecen en su carpeta.', 'body.small', 'muted')
        body.addWidget(self.status)
        self.rows_widget = QWidget()
        self.rows = QVBoxLayout(self.rows_widget)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(metric('spacing.extraSmall'))
        body.addWidget(self.rows_widget)
        body.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        foot = QHBoxLayout()
        tagline = label('Lectura con intención', 'label.small', 'muted')
        tagline.setWordWrap(False)
        foot.addWidget(tagline)
        foot.addStretch()
        privacy = label('Archivos locales · Sin cuenta', 'label.small', 'muted')
        privacy.setWordWrap(False)
        foot.addWidget(privacy)
        outer.addLayout(foot)

    def refresh(self):
        try:
            self.books = self.store.recent() if self.store else []
        except STORAGE_ERRORS as error:
            self.message.emit(str(error))
            return
        self.heading.setText('Vuelve al hilo\nde tus ideas.' if self.books else 'Una lectura.\nMuchas ideas.')
        if self.books:
            book = self.books[0]
            self.eyebrow.setText('CONTINÚA DONDE LO DEJASTE')
            self.book_title.setText(book['title'])
            self.meta.setText(f'Página {book["page"]+1} de {book["pages"]}  ·  {book["notes"]} notas en tu cuaderno')
            self.continue_button.set_content('arrow_forward', 'Continuar lectura')
        else:
            self.eyebrow.setText('EMPIEZA POR LO QUE TE DA CURIOSIDAD')
            self.book_title.setText('Tu próximo capítulo empieza aquí')
            self.meta.setText('Lee con calma. Conecta una idea con otra.\nGuarda tus reflexiones junto al pasaje.')
            self.continue_button.set_content('folder_open', 'Abrir mi primer PDF')
        self.filter()

    def filter(self):
        while self.rows.count():
            item = self.rows.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()
        books = [b for b in self.books if self.search.text().casefold() in b['title'].casefold()]
        self.status.setText(f'{len(books)} documentos · Ordenados por última apertura' if books else
                            'No hay resultados. Prueba otro título.' if self.search.text() else
                            'Los documentos que abras aparecerán aquí. Tus originales permanecen en su carpeta.')
        for book in books:
            self.rows.addWidget(BookRow(book, self.open_requested.emit, self.forget))

    def forget(self, identifier):
        try:
            self.store.forget(identifier)
            self.refresh()
        except STORAGE_ERRORS as error:
            self.message.emit(str(error))

    def continue_reading(self):
        if self.books:
            self.open_requested.emit(self.books[0]['path'])
        else:
            self.choose_requested.emit()

    def resizeEvent(self, event):
        self.art.setVisible(self.width() >= metric('spacing.extraExtraLarge', 16))
        super().resizeEvent(event)


class Notebook(Panel):
    jump = Signal(object)
    closed = Signal()
    message = Signal(str)
    export_requested = Signal()
    new_requested = Signal()

    def __init__(self, store):
        super().__init__()
        self.store, self.document, self.entry = store, None, None
        self.anchor, self.quote, self.page = {}, '', 0
        self.unsaved = False
        self.setMinimumWidth(metric('spacing.extraExtraLarge', 6))
        self.setMaximumWidth(metric('spacing.extraExtraLarge', 8))
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        outer = layout(content)
        self.page_scroll.setWidget(content)
        shell.addWidget(self.page_scroll)
        top = QHBoxLayout()
        top.addWidget(label('Cuaderno', 'title.large'), 1)
        top.addWidget(IconButton('ios_share', 'Exportar cuaderno', self.export_requested.emit, size=control_height()))
        top.addWidget(IconButton('close', 'Cerrar cuaderno', self.closed.emit, size=control_height()))
        outer.addLayout(top)
        outer.addWidget(label('TUS IDEAS, JUNTO AL TEXTO', 'label.small', 'accent'))
        self.source = label('Añade una reflexión o selecciona un pasaje.', 'body.small', 'muted')
        outer.addWidget(self.source)
        self.quote_label = label('', 'body.small')
        self.quote_label.setMaximumHeight(metric('spacing.extraExtraLarge', 2))
        outer.addWidget(self.quote_label)
        kind_row = QHBoxLayout()
        self.kind = 'note'
        self.kind_button = PillButton('edit_note', 'Reflexión', self.toggle_kind, 'tonal', control_height())
        kind_row.addWidget(self.kind_button)
        kind_row.addStretch()
        outer.addLayout(kind_row)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName('Tu reflexión')
        self.editor.setPlaceholderText('¿Qué significa para ti?\nEscribe con tus propias palabras…')
        self.editor.setFont(text_font('body.medium'))
        self.editor.setMinimumHeight(metric('spacing.extraExtraLarge', 2))
        self.editor.setMaximumHeight(metric('spacing.extraExtraLarge', 4))
        extend_style(self.editor, 'QPlainTextEdit {background:@well;color:@text;border:@border.width solid @line;'
                     'border-radius:@rounding.medium;padding:@padding.medium;}'
                     'QPlainTextEdit:focus {border:@border.focus solid @focus;}')
        self.editor.textChanged.connect(self.changed)
        outer.addWidget(self.editor)
        self.status = label('Las notas se guardan en tu biblioteca local.', 'label.small', 'muted')
        outer.addWidget(self.status)
        actions = QHBoxLayout()
        self.save_button = PillButton('check', 'Guardar nota', self.save, height=control_height())
        self.save_button.setEnabled(False)
        actions.addWidget(self.save_button)
        self.copy_button = IconButton('content_copy', 'Guardar como nota nueva', self.save_as_new,
                                      variant='tonal', size=control_height())
        self.copy_button.hide()
        actions.addWidget(self.copy_button)
        actions.addWidget(IconButton('add', 'Nueva reflexión', self.new_requested.emit, variant='tonal', size=control_height()))
        outer.addLayout(actions)
        self.list_widget = QWidget()
        self.items = layout(self.list_widget, padding='padding.extraSmall')
        outer.addWidget(self.list_widget, 1)
        # Deliberately explicit Save in this first slice: no background draft overwrite.
        # Navigation calls can_leave; failed writes leave the editor intact.

    def changed(self):
        self.unsaved = True
        self.save_button.setEnabled(bool(self.editor.toPlainText().strip()) and bool(self.document))
        self.status.setText('Nota sin guardar · el PDF se guarda por separado')

    def toggle_kind(self):
        self.kind = 'question' if self.kind == 'note' else 'note'
        self.kind_button.set_content('help' if self.kind == 'question' else 'edit_note',
                                     'Pregunta' if self.kind == 'question' else 'Reflexión')
        if self.editor.toPlainText():
            self.changed()

    def can_leave(self):
        if not self.unsaved:
            return True
        choice = QMessageBox.question(self, 'Nota sin guardar', '¿Guardar tu reflexión antes de continuar?',
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if choice == QMessageBox.Save:
            return self.save()
        if choice == QMessageBox.Discard:
            self.unsaved = False
            return True
        return False

    def bind(self, document):
        self.document = document
        self.entry = None
        self.reset_editor()
        self.refresh()

    def reset_editor(self, page=0, quote='', anchor=None, entry=None):
        self.entry, self.page, self.quote, self.anchor = entry, page, quote, anchor or {}
        self.kind = entry['kind'] if entry else 'note'
        self.kind_button.set_content('help' if self.kind == 'question' else 'edit_note',
                                     'Pregunta' if self.kind == 'question' else 'Reflexión')
        self.editor.setPlainText(entry['body'] if entry else '')
        self.quote_label.setText(quote)
        self.quote_label.setVisible(bool(quote))
        self.source.setText(f'Página {page+1} · Este libro')
        self.status.setText('Nota guardada en tu biblioteca' if entry else 'Las notas se guardan en tu biblioteca local.')
        self.save_button.setEnabled(False)
        self.copy_button.hide()
        self.unsaved = False

    def new(self, page=None, quote='', anchor=None):
        if not self.can_leave():
            return False
        self.reset_editor(self.page if page is None else page, quote, anchor)
        self.editor.setFocus()
        return True

    def save(self):
        if not self.document or not self.editor.toPlainText().strip():
            self.status.setText('Escribe una idea antes de guardarla.')
            return False
        try:
            self.entry = self.store.save_entry(self.document['id'], self.page, self.quote, self.anchor,
                                              self.editor.toPlainText(), self.kind, self.entry)
        except StudyConflict as error:
            self.status.setText(str(error))
            self.copy_button.show()
            return False
        except STORAGE_ERRORS as error:
            self.status.setText(str(error))
            return False
        self.unsaved = False
        self.save_button.setEnabled(False)
        self.copy_button.hide()
        self.status.setText('Cuaderno guardado · independiente del PDF')
        self.refresh()
        return True

    def save_as_new(self):
        original = self.entry
        self.entry = None
        if not self.save():
            self.entry = original

    def refresh(self):
        while self.items.count():
            child = self.items.takeAt(0)
            if child.widget():
                child.widget().hide()
                child.widget().deleteLater()
        try:
            entries = self.store.entries(self.document['id']) if self.document and self.store else []
        except STORAGE_ERRORS as error:
            self.message.emit(str(error))
            return
        self.items.addWidget(label(f'{len(entries)} ideas para volver a pensar', 'label.small', 'muted'))
        for entry in entries:
            button = PillButton('help' if entry['kind'] == 'question' else 'edit_note',
                                f'Página {entry["page"]+1}', lambda e=entry: self.edit(e), 'tonal', control_height())
            self.items.addWidget(button)
            self.items.addWidget(label(entry['body'][:240], 'body.small'))
            row = QHBoxLayout()
            jump = IconButton('arrow_back', 'Volver al pasaje', lambda e=entry: self.jump.emit(e), size=control_height())
            row.addWidget(jump)
            row.addStretch()
            row.addWidget(IconButton('delete', 'Eliminar nota', lambda e=entry: self.remove(e), size=control_height()))
            box = QWidget()
            box.setLayout(row)
            self.items.addWidget(box)
        self.items.addStretch()

    def edit(self, entry):
        if self.can_leave():
            self.reset_editor(entry['page'], entry['quote'], json.loads(entry['anchor']), entry)
            self.editor.setFocus()

    def remove(self, entry):
        if self.unsaved and not self.can_leave():
            return
        if QMessageBox.question(self, 'Eliminar nota', '¿Eliminar esta nota del cuaderno?',
                                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
            return
        try:
            self.store.delete_entry(entry)
        except STORAGE_ERRORS as error:
            self.message.emit(str(error))
            return
        if self.entry and self.entry['id'] == entry['id']:
            self.reset_editor()
        self.refresh()


class StudySettings(QDialog):
    """Only settings that already work; roadmap features never masquerade as controls."""
    def __init__(self, preferences, store, parent=None):
        super().__init__(parent)
        self.preferences, self.store = preferences, store
        self.setWindowTitle('Ajustes de estudio')
        apply_kit_style(self)
        self.setMinimumWidth(metric('spacing.extraExtraLarge', 10))
        outer = layout(self, padding='padding.extraLarge')
        outer.addWidget(label('A tu manera', 'headline.medium'))
        outer.addWidget(label('Biblioteca y datos', 'title.medium'))
        self.remember = QCheckBox('Recordar documentos recientes')
        self.remember.setChecked(preferences.get('remember_recent', True) is not False)
        self.remember.toggled.connect(self.set_remember)
        outer.addWidget(self.remember)
        outer.addWidget(label('La posición de lectura y tus notas se conservan aunque desactives los recientes.',
                              'body.small', 'muted'))
        clear = PillButton('delete', 'Limpiar recientes', self.clear, 'tonal', control_height())
        clear.setEnabled(store is not None)
        outer.addWidget(clear, 0, Qt.AlignLeft)
        outer.addWidget(label('Tus ideas son tuyas', 'title.medium'))
        outer.addWidget(label('El cuaderno se guarda en tu biblioteca local. Los subrayados y las notas '
                              'colocadas en la página se guardan dentro del PDF. Puedes exportar el cuaderno '
                              'a Markdown desde su panel.', 'body.medium'))
        outer.addWidget(label('Material You', 'title.medium'))
        outer.addWidget(label('La interfaz sigue los colores del escritorio. El papel conserva el aspecto '
                              'original del documento. Las transiciones respetan el movimiento reducido de Wysun.',
                              'body.small', 'muted'))
        self.status = label('', 'body.small', 'muted')
        outer.addWidget(self.status)
        outer.addWidget(PillButton('check', 'Listo', self.accept, height=control_height()), 0, Qt.AlignRight)

    def set_remember(self, checked):
        try:
            self.preferences.set(remember_recent=checked)
        except STORAGE_ERRORS as error:
            self.status.setText(str(error))
            self.remember.blockSignals(True)
            self.remember.setChecked(not checked)
            self.remember.blockSignals(False)

    def clear(self):
        if QMessageBox.question(self, 'Limpiar recientes',
                'Se quitará la lista de recientes. Tus PDF y tus notas se conservarán.',
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
            return
        try:
            self.store.clear_recent()
            self.status.setText('Lista de recientes vaciada. Los archivos y las notas se conservan.')
        except STORAGE_ERRORS as error:
            self.status.setText(str(error))

