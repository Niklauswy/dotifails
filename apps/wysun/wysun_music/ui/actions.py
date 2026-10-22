"""User intents shared by every page: play a context, menus, playlist edits."""
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

from music_library import artists


class Actions(QObject):
    navigate = Signal(tuple)
    show_player = Signal(str)   # open «Ahora suena» on a tab

    def __init__(self, library, covers, player, host):
        super().__init__(host)
        self.library, self.covers, self.player = library, covers, player
        self.host = host  # parent widget for menus and dialogs

    # ---------------------------------------------------------------- playing
    def is_playing(self, collection_id):
        return self.player.playing and self.player.queue.context == collection_id

    def play_collection(self, collection, start=None, shuffle=None):
        self.player.play_collection(collection.keys, start, collection.id, shuffle)

    def toggle_collection(self, collection):
        """The big play button: pause/resume its own context, or start it."""
        if self.player.current and self.player.queue.context == collection.id:
            self.player.toggle()
        else:
            self.play_collection(collection)

    def play_track(self, key):
        self.player.play(key, self.library.all_keys(), 'all')

    def shuffle_library(self):
        """«Mezcla»: the whole library in random order."""
        self.player.play_collection(self.library.all_keys(), context='all', shuffle=True)

    # ------------------------------------------------------------------ menus
    def _menu(self):
        return QMenu(self.host)

    def track_menu(self, keys, position, collection=None):
        if not keys:
            return
        menu = self._menu()
        single = len(keys) == 1
        key = keys[0]
        if single:
            menu.addAction('Reproducir', lambda: self.player.play(key, collection.keys if collection else [key],
                                                                     collection.id if collection else None))
        menu.addAction('Reproducir a continuación', lambda: self.player.play_next(keys))
        menu.addAction('Añadir a la cola', lambda: self.player.add_to_queue(keys))
        menu.addSeparator()
        playlists = menu.addMenu('Añadir a playlist')
        playlists.addAction('Nueva playlist…', lambda: self.new_playlist(keys))
        user = [c for c in self.library.collections() if c.editable]
        if user:
            playlists.addSeparator()
        for target in user:
            playlists.addAction(target.title, lambda target=target: self.library.add_to_playlist(target.id, keys))
        if collection is not None and collection.editable:
            menu.addAction('Quitar de esta playlist', lambda: self.library.remove_from_playlist(collection.id, keys))
        favorite = all(k in self.library.favorites for k in keys)
        menu.addAction('Quitar de Tus me gusta' if favorite else 'Guardar en Tus me gusta',
                       lambda: self.set_favorite(keys, not favorite))
        if single:
            menu.addSeparator()
            names = artists(self.library.track(key))
            if len(names) == 1:
                menu.addAction('Ir al artista', lambda: self.navigate.emit(('collection', 'artist:' + names[0])))
            elif names:
                go = menu.addMenu('Ir al artista')
                for name in names:
                    go.addAction(name, lambda name=name: self.navigate.emit(('collection', 'artist:' + name)))
            menu.addAction('Mostrar en la carpeta', lambda: self.show_in_folder(key))
        menu.exec(position)

    def collection_menu(self, collection, position):
        menu = self._menu()
        menu.addAction('Reproducir', lambda: self.play_collection(collection))
        menu.addAction('Reproducir en aleatorio', lambda: self.play_collection(collection, shuffle=True))
        menu.addAction('Añadir a la cola', lambda: self.player.add_to_queue(collection.keys))
        if collection.editable:
            menu.addSeparator()
            menu.addAction('Cambiar nombre…', lambda: self.rename_playlist(collection))
            menu.addAction('Eliminar playlist', lambda: self.delete_playlist(collection))
        if collection.source.startswith('https://'):
            menu.addSeparator()
            menu.addAction('Abrir en Spotify', lambda: QDesktopServices.openUrl(QUrl(collection.source)))
        menu.exec(position)

    def set_favorite(self, keys, favorite):
        for key in keys:
            if (key in self.library.favorites) != favorite:
                self.library.toggle_favorite(key)

    # -------------------------------------------------------------- playlists
    def new_playlist(self, keys=()):
        count = sum(c.editable for c in self.library.collections()) + 1
        title, accepted = QInputDialog.getText(self.host, 'Nueva playlist', 'Nombre', text=f'Mi playlist n.º {count}')
        if accepted:
            key = self.library.create_playlist(title, keys)
            if not keys:
                self.navigate.emit(('collection', key))

    def rename_playlist(self, collection):
        title, accepted = QInputDialog.getText(self.host, 'Cambiar nombre', 'Nombre', text=collection.title)
        if accepted:
            self.library.rename_playlist(collection.id, title)

    def delete_playlist(self, collection):
        answer = QMessageBox.question(self.host, 'Eliminar playlist',
                                      f'¿Eliminar «{collection.title}»? Las canciones siguen en tu biblioteca.')
        if answer == QMessageBox.Yes:
            self.library.delete_playlist(collection.id)
            self.navigate.emit(('home',))

    def show_in_folder(self, key):
        path = self.library.playable(key).get('path')
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))
