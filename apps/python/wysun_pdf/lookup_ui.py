"""A source-attributed lookup beside the current passage, with explicit online consent."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QMessageBox
from wysun_core.ui.panels import Panel
from wysun_core.ui.widgets import PillButton, IconButton
from wysun_core.ui.style import metric
from wysun_pdf.study_ui import label, layout, control_height, STORAGE_ERRORS
from wysun_pdf.lookup import LookupClient, request_url


class LookupPanel(Panel):
    closed = Signal()
    open_url = Signal(str)
    save_requested = Signal(object)

    def __init__(self, preferences):
        super().__init__()
        self.preferences = preferences
        self.kind, self.source, self.target = 'translation', 'en', 'es'
        self.client = LookupClient(self)
        self.client.completed.connect(self.results)
        self.client.failed.connect(self.error)
        self.setMinimumWidth(metric('spacing.extraExtraLarge', 6))
        self.setMaximumWidth(metric('spacing.extraExtraLarge', 8))
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        outer = layout(content)
        scroll.setWidget(content)
        shell.addWidget(scroll)
        top = QHBoxLayout()
        top.addWidget(label('Consulta', 'title.large'), 1)
        top.addWidget(IconButton('close', 'Cerrar consulta', self.closed.emit, size=control_height()))
        outer.addLayout(top)
        outer.addWidget(label('OTRA PISTA PARA COMPRENDER', 'label.small', 'accent'))
        self.term = QLineEdit()
        self.term.setPlaceholderText('Palabra o concepto')
        self.term.setAccessibleName('Texto para consultar')
        self.term.setMaxLength(500)
        self.term.textChanged.connect(self.invalidate)
        self.term.returnPressed.connect(self.search)
        outer.addWidget(self.term)
        modes = QHBoxLayout()
        self.mode_button = PillButton('translate', 'Traducir', lambda: self.set_kind('translation'), 'filled', control_height())
        self.concept_button = PillButton('travel_explore', 'Concepto', lambda: self.set_kind('concept'), 'tonal', control_height())
        modes.addWidget(self.mode_button)
        modes.addWidget(self.concept_button)
        outer.addLayout(modes)
        languages = QHBoxLayout()
        languages.addWidget(label('Idioma', 'body.small', 'muted'), 1)
        self.languages = PillButton('swap_horiz', 'EN → ES', self.swap, 'tonal', control_height())
        languages.addWidget(self.languages)
        outer.addLayout(languages)
        self.status = label('Solo se envía el texto que consultas, cuando pulsas Buscar.', 'body.small', 'muted')
        outer.addWidget(self.status)
        self.search_button = PillButton('search', 'Buscar', self.search, height=control_height())
        outer.addWidget(self.search_button)
        self.cancel_button = PillButton('close', 'Cancelar consulta', self.cancel, 'tonal', control_height())
        self.cancel_button.hide()
        outer.addWidget(self.cancel_button)
        self.result_widget = QWidget()
        self.result_layout = layout(self.result_widget, padding='padding.extraSmall')
        outer.addWidget(self.result_widget)
        outer.addStretch()

    def invalidate(self):
        self.client.cancel()
        self.cancel_button.hide()
        self.clear_results()
        self.status.setText('Solo se envía el texto que consultas, cuando pulsas Buscar.')

    def clear_results(self):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def set_term(self, text):
        self.invalidate()
        self.term.setText(text)
        self.term.setFocus()

    def set_kind(self, kind):
        if kind == self.kind:
            return
        self.kind = kind
        self.mode_button.variant = 'filled' if kind == 'translation' else 'tonal'
        self.concept_button.variant = 'filled' if kind == 'concept' else 'tonal'
        self.mode_button.update()
        self.concept_button.update()
        self.update_language_label()
        self.invalidate()

    def swap(self):
        self.source, self.target = self.target, self.source
        self.update_language_label()
        self.invalidate()

    def update_language_label(self):
        self.languages.set_content('swap_horiz', self.target.upper() if self.kind == 'concept' else
                                    f'{self.source.upper()} → {self.target.upper()}')

    def search(self):
        text = self.term.text().strip()
        try:
            request_url(self.kind, text, self.source, self.target)
        except ValueError as error:
            self.error(str(error))
            return
        provider = 'MyMemory (Translated)' if self.kind == 'translation' else 'Wikipedia'
        permission = 'lookup_allowed_' + self.kind
        if not self.preferences.get(permission, False):
            prompt = (f'Se enviará este texto a {provider}:\n\n{text}\n\n'
                      'No se envía el PDF ni tu cuaderno. El proveedor puede procesar y registrar la consulta. '
                      'Puedes revocar este permiso en Ajustes. ¿Permitir consultas a este proveedor?')
            if QMessageBox.question(self, 'Consulta online', prompt,
                    QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                return
            try:
                self.preferences.set(**{permission: True})
            except STORAGE_ERRORS as error:
                self.error(str(error))
                return
        self.clear_results()
        self.status.setText(f'Consultando {provider}…')
        self.cancel_button.show()
        self.client.search(self.kind, text, self.source, self.target)

    def cancel(self):
        self.client.cancel()
        self.cancel_button.hide()
        self.status.setText('Consulta cancelada.')

    def error(self, message):
        self.cancel_button.hide()
        self.status.setText(message)

    def results(self, results):
        self.clear_results()
        self.cancel_button.hide()
        self.status.setText('Sin resultados. Prueba un término más concreto.' if not results else
                            'Consulta la fuente para profundizar y contrastar el contexto.')
        for result in results:
            self.result_layout.addWidget(label(result['title'], 'title.medium'))
            self.result_layout.addWidget(label(result['body'], 'body.medium'))
            self.result_layout.addWidget(label(result['attribution'], 'label.small', 'muted'))
            self.result_layout.addWidget(PillButton('open_in_new', 'Abrir fuente',
                lambda r=result: self.open_url.emit(r['url']), 'tonal', control_height()))
            self.result_layout.addWidget(PillButton('add', 'Guardar en cuaderno',
                lambda r=result: self.save_requested.emit(dict(r, term=self.term.text(), language=self.target,
                                                               kind=self.kind)), 'tonal', control_height()))
