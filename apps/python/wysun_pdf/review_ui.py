"""Search the whole notebook and practise questions without automatic grading."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPlainTextEdit, QScrollArea, QWidget
from wysun_core.qt_theme import extend_style
from wysun_core.ui.style import apply_kit_style, metric, text_font
from wysun_core.ui.widgets import PillButton
from wysun_core.ui.panels import SearchField
from wysun_pdf.study_ui import label, layout, control_height, count, STORAGE_ERRORS


class AnswerDialog(QDialog):
    """Esc or closing the window never silently discards a typed answer."""
    editor = None

    def reject(self):
        if (self.editor is not None and self.editor.toPlainText().strip() and
                QMessageBox.question(self, 'Respuesta sin guardar', '¿Descartar lo que escribiste?',
                                     QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Discard):
            return
        super().reject()


class ReviewDialog(QDialog):
    passage_requested = Signal(object)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.questions, self.current = store, False, None
        self.visible_limit = 100
        self.setWindowTitle('Cuaderno global y repaso')
        apply_kit_style(self)
        extend_style(self, 'QDialog {background:@surface;}')
        self.resize(metric('spacing.extraExtraLarge', 16), metric('spacing.extraExtraLarge', 14))
        outer = layout(self)
        outer.addWidget(label('Ideas que se conectan', 'headline.medium'))
        outer.addWidget(label('Todos tus libros, incluso los que quitaste de recientes.', 'body.small', 'muted'))
        row = QHBoxLayout()
        self.search = SearchField('Buscar en todos los cuadernos')
        self.search.setPlaceholderText('Libro, concepto o #etiqueta')
        self.search.textChanged.connect(self.refresh)
        row.addWidget(self.search, 1)
        self.mode = PillButton('psychology', 'Repasar preguntas', self.toggle, 'tonal', control_height())
        row.addWidget(self.mode)
        outer.addLayout(row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        self.items = layout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.status = label('', 'body.small', 'muted')
        outer.addWidget(self.status)
        outer.addWidget(PillButton('check', 'Listo', self.accept, height=control_height()), 0, Qt.AlignRight)
        self.refresh()

    def toggle(self):
        self.questions = not self.questions
        self.mode.set_content('menu_book' if self.questions else 'psychology',
                              'Ver todas las notas' if self.questions else 'Repasar preguntas')
        self.refresh()

    def refresh(self):
        while self.items.count():
            item = self.items.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        try:
            entries = self.store.all_entries(self.search.text(), self.questions) if self.store else []
        except STORAGE_ERRORS as error:
            self.status.setText(str(error))
            return
        self.status.setText(count(len(entries), 'idea', 'ideas') if entries else
                            'Sin resultados. Guarda preguntas desde el cuaderno de un libro.')
        for entry in entries[:self.visible_limit]:
            card = QWidget()
            column = layout(card, padding='padding.extraSmall')
            column.setSpacing(metric('spacing.small'))
            column.addWidget(label(f'{entry["title"]} · página {entry["page"] + 1}', 'label.small', 'accent'))
            column.addWidget(label(entry['body'], 'body.medium'))
            if entry['quote'] and not self.questions:
                column.addWidget(label(entry['quote'], 'body.small', 'muted'))
            actions = QHBoxLayout()
            if self.questions:
                state = 'Comprendido' if entry['understood'] else 'Por estudiar'
                actions.addWidget(PillButton('psychology', state + ' · Responder',
                    lambda checked=False, e=entry: self.answer(e), 'tonal', control_height()))
            actions.addWidget(PillButton('arrow_forward', 'Volver al pasaje',
                lambda checked=False, e=entry: self.passage_requested.emit(e), 'tonal', control_height()))
            actions.addStretch()
            column.addLayout(actions)
            self.items.addWidget(card)
        if len(entries) > self.visible_limit:
            self.items.addWidget(PillButton('expand_more', 'Mostrar más ideas', self.show_more, 'tonal', control_height()),
                                 0, Qt.AlignLeft)
        self.items.addStretch()

    def show_more(self):
        self.visible_limit += 100
        self.refresh()

    def answer(self, entry):
        dialog = AnswerDialog(self)
        dialog.setWindowTitle('Repasar con tus propias palabras')
        apply_kit_style(dialog)
        extend_style(dialog, 'QDialog {background:@surface;}')
        outer = layout(dialog)
        outer.addWidget(label(entry['body'], 'title.medium'))
        editor = QPlainTextEdit()
        editor.setFont(text_font('body.medium'))
        extend_style(editor, 'QPlainTextEdit {background:@well;color:@text;border:@border.width solid @line;'
                     'border-radius:@rounding.medium;padding:@padding.medium;}')
        editor.setAccessibleName('Tu respuesta')
        editor.setPlaceholderText('Intenta responder antes de mirar el pasaje…')
        dialog.editor = editor
        outer.addWidget(editor)
        source = label(entry['quote'] or 'Esta pregunta no tiene una cita asociada.', 'body.small', 'muted')
        source.hide()
        outer.addWidget(source)
        def reveal():
            source.show()
            if entry['answer']:
                source.setText(source.text() + '\n\nRespuesta anterior: ' + entry['answer'])
            reveal_button.setEnabled(False)
        reveal_button = PillButton('visibility', 'Mostrar cita y respuesta anterior', reveal, 'tonal', control_height())
        outer.addWidget(reveal_button, 0, Qt.AlignLeft)
        status = label('', 'body.small', 'muted')
        outer.addWidget(status)
        def save(understood):
            try:
                self.store.review(entry['id'], editor.toPlainText() or entry['answer'], understood)
            except STORAGE_ERRORS as error:
                status.setText(str(error))
                return
            dialog.accept()
        choices = QHBoxLayout()
        choices.addStretch()
        choices.addWidget(PillButton('bookmark', 'Seguir estudiando', lambda: save(False), 'tonal', control_height()))
        choices.addWidget(PillButton('check', 'Lo comprendí', lambda: save(True), height=control_height()))
        outer.addLayout(choices)
        dialog.resize(metric('spacing.extraExtraLarge', 11), metric('spacing.extraExtraLarge', 12))
        dialog.exec()
        self.refresh()
