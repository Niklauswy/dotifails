"""Wysun Files as a file chooser (F-62…F-67): the same window in selector mode, for the portal
(``service.py``) and the one-shot picker (``picker.py``). The rules are ``core.chooser.ChooserSession``'s; this
bridge applies its filters to the folder model, turns the user's choice into the portal's reply and never
writes a file. ``completed(code, result)`` is emitted exactly once: 0 with the result, 1 when cancelled."""
from PySide6.QtCore import Property, QObject, Signal, Slot, QUrl

from wysun_files.core.chooser import ChooserSession


class Chooser(QObject):
    completed = Signal(int, object)
    changed = Signal()
    confirmRequested = Signal(str, str)          # name, folder

    def __init__(self, session, controller, parent=None):
        super().__init__(parent)
        self.session = session
        self.controller = controller
        self._error = ''
        self._pending = []
        self._values = {ident: selected for ident, _label, _entries, selected in session.choices}
        self._done = False
        self._apply_filter()

    def _apply_filter(self):
        session = self.session
        for tab in self.controller.property('tabs'):
            tab.model.set_accept(lambda entry: session.accepts(entry.path, entry.is_dir))

    # ---------------------------------------------------------------- what QML shows
    @Property(str, constant=True)
    def title(self):
        return self.session.title

    @Property(str, constant=True)
    def mode(self):
        return self.session.mode

    @Property(bool, constant=True)
    def directory(self):
        return self.session.directory

    @Property(bool, constant=True)
    def multiple(self):
        return self.session.multiple

    @Property(str, constant=True)
    def acceptLabel(self):
        return self.session.accept_label

    @Property(str, constant=True)
    def currentName(self):
        return self.session.current_name

    @Property('QVariantList', constant=True)
    def filters(self):
        return [name for name, _rules in self.session.filters]

    @Property(int, notify=changed)
    def filterIndex(self):
        return self.session.filter_index

    @Property('QVariantList', notify=changed)
    def choices(self):
        out = []
        for ident, label, entries, _selected in self.session.choices:
            value = self._values.get(ident, '')
            options = [{'value': v, 'text': t} for v, t in entries]
            shown = next((o['text'] for o in options if o['value'] == value), value)
            out.append({'id': ident, 'label': label, 'options': options, 'value': value, 'text': shown,
                        'toggle': not entries})
        return out

    @Property(str, notify=changed)
    def error(self):
        return self._error

    # ---------------------------------------------------------------- changes
    @Slot(int)
    def setFilter(self, index):
        if 0 <= index < len(self.session.filters):
            self.session.filter_index = index
            self._apply_filter()
            self.changed.emit()

    @Slot(str, str)
    def setChoice(self, ident, value):
        self._values[ident] = str(value)
        self.changed.emit()

    # ---------------------------------------------------------------- answering
    @Slot(str, 'QVariantList', str)
    def accept(self, folder, selected, name=''):
        state, value = self.session.resolve(folder, list(selected), name)
        if state == 'error':
            self._error = value
            self.changed.emit()
        elif state == 'confirm':
            self._pending = value
            self.confirmRequested.emit(value[0].name, value[0].parent.name or str(value[0].parent))
        else:
            self._finish(value)

    @Slot()
    def confirmReplace(self):
        if self._pending:
            targets, self._pending = self._pending, []
            self._finish(targets)

    def _finish(self, targets):
        code, result = self.session.result(targets, self._values)
        self._error = ''
        self._reply(code, result)

    @Slot()
    def cancel(self):
        self._reply(1, {})

    def _reply(self, code, result):
        if self._done:
            return
        self._done = True
        self.completed.emit(code, result)

    @Property(bool, notify=changed)
    def done(self):
        return self._done


class QmlChooserWindow:
    """A chooser window: its own engine, controller and places, and Chooser.qml (shared parts with Main.qml)."""

    def __init__(self, mode, title, options, settings=None, thumbnails=True):
        from wysun_qml import engine as qml_engine, theme_bridge
        from .controller import FilesController
        from .places import Places
        from .preview import Preview
        from .window import qml_dir
        self.session = ChooserSession(mode, title, options)
        self.app, self.engine = qml_engine.create_engine('wysun-files')
        self.bridge = theme_bridge.ThemeBridge(parent=self.engine)
        self.files = FilesController([self.session.initial_folder], settings=settings, thumbnails=thumbnails,
                                     parent=self.engine)
        self.places = Places(settings=self.files.settings, parent=self.engine)
        self.preview = Preview(parent=self.engine)
        self.chooser = Chooser(self.session, self.files, parent=self.engine)
        context = self.engine.rootContext()
        for name, value in {'bridge': self.bridge, 'files': self.files, 'places': self.places, 'preview': self.preview,
                            'chooser': self.chooser}.items():
            context.setContextProperty(name, value)
        before = len(self.engine.rootObjects())
        self.engine.load(QUrl.fromLocalFile(str(qml_dir() / 'Chooser.qml')))
        roots = self.engine.rootObjects()
        if len(roots) <= before:
            raise RuntimeError('Wysun Files: Chooser.qml did not load')
        self.window = roots[-1]
        self.chooser.completed.connect(lambda *_: self.window.hide())

    def present(self):
        from PySide6.QtGui import QCursor, QGuiApplication
        window = self.window
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        window.resize(min(1100, int(area.width() * .82)), min(740, int(area.height() * .82)))
        window.setPosition(area.x() + (area.width() - window.width()) // 2, area.y() + (area.height() - window.height()) // 2)
        window.show()
        window.raise_()
        window.requestActivate()

    def close(self):
        """Cancel if nothing was chosen, then release everything."""
        self.chooser.cancel()
        self.window.hide()
        self.preview.close()
        self.places.close()
        self.files.close()
