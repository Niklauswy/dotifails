// The menus of Wysun Music, in window coordinates: a song (or a selection), a collection, «Añadir a playlist»,
// «Ir al artista» with several artists, and the sort order. Entries follow the Widgets UI (M-35, M-37).
import QtQuick
import WysunM3

Item {
    id: root

    property var app
    property Item host
    property var _keys: []
    property string _collection
    property var _sortApply
    property var _summary: ({})

    function trackMenu(keys, collectionId, x, y) {
        if (!keys || keys.length === 0)
            return;
        _keys = keys;
        _collection = collectionId || "";
        const single = keys.length === 1;
        const summary = _collection ? music.collectionSummary(_collection) : {};
        const favorite = music.allFavorite(keys);
        const names = single ? music.trackArtists(keys[0]) : [];
        const entries = [];
        if (single)
            entries.push({id: "play", text: "Reproducir", icon: "play_arrow"});
        entries.push({id: "next", text: "Reproducir a continuación", icon: "playlist_play"});
        entries.push({id: "queue", text: "Añadir a la cola", icon: "add_to_queue"});
        entries.push({divider: true});
        entries.push({id: "playlist", text: "Añadir a playlist", icon: "playlist_add", shortcut: "›"});
        if (summary.editable)
            entries.push({id: "remove", text: "Quitar de esta playlist", icon: "playlist_remove"});
        entries.push({id: "favorite", text: favorite ? "Quitar de Tus me gusta" : "Guardar en Tus me gusta", icon: "favorite"});
        if (single) {
            entries.push({divider: true});
            if (names.length === 1)
                entries.push({id: "artist:" + names[0], text: "Ir al artista", icon: "artist"});
            else if (names.length > 1)
                entries.push({id: "artists", text: "Ir al artista", icon: "artist", shortcut: "›"});
            entries.push({id: "folder", text: "Mostrar en la carpeta", icon: "folder_open"});
        }
        trackPopup.model = entries;
        trackPopup.popup(null, x, y);
    }

    function playlistMenu(keys, x, y) {
        _keys = keys;
        const entries = [{id: "new", text: "Nueva playlist…", icon: "add"}];
        const lists = music.editablePlaylists();
        if (lists.length > 0)
            entries.push({divider: true});
        for (const list of lists)
            entries.push({id: list.id, text: list.title, icon: "queue_music"});
        playlistPopup.model = entries;
        playlistPopup.popup(null, x, y);
    }

    function collectionMenu(id, item, x, y) {
        _summary = music.collectionSummary(id);
        if (!_summary.id)
            return;
        const entries = [{id: "play", text: "Reproducir", icon: "play_arrow"}, {id: "shuffle", text: "Reproducir en aleatorio", icon: "shuffle"}, {id: "queue", text: "Añadir a la cola", icon: "add_to_queue"}];
        if (_summary.editable) {
            entries.push({divider: true});
            entries.push({id: "rename", text: "Cambiar nombre…", icon: "edit"});
            entries.push({id: "delete", text: "Eliminar playlist", icon: "delete"});
        }
        if (_summary.source) {
            entries.push({divider: true});
            entries.push({id: "spotify", text: "Abrir en Spotify", icon: "open_in_new"});
        }
        collectionPopup.model = entries;
        collectionPopup.popup(item, x, y);
    }

    function sortMenu(current, apply, x, y) {
        _sortApply = apply;
        sortPopup.model = [["custom", "Orden personalizado"], ["title", "Título"], ["artist", "Artista"], ["album", "Álbum"], ["duration", "Duración"]].map(e => ({
                    id: e[0],
                    text: e[1],
                    icon: e[0] === current ? "check" : ""
                }));
        sortPopup.popup(null, x, y);
    }

    Menu {
        id: trackPopup

        objectName: "trackMenu"
        host: root.host
        onTriggered: id => {
            const keys = root._keys;
            const at = Qt.point(panelX + panelWidth / 2, panelY + Metrics.menuItemHeight);
            if (id === "play")
                player.play(keys[0], root._collection ? music.collectionSummary(root._collection).keys : [keys[0]], root._collection);
            else if (id === "next")
                player.playNext(keys);
            else if (id === "queue")
                player.addToQueue(keys);
            else if (id === "playlist")
                root.playlistMenu(keys, at.x, at.y);
            else if (id === "remove")
                music.removeFromPlaylist(root._collection, keys);
            else if (id === "favorite")
                music.setFavorite(keys, !music.allFavorite(keys));
            else if (id === "folder")
                music.showInFolder(keys[0]);
            else if (id === "artists") {
                artistPopup.model = music.trackArtists(keys[0]).map(n => ({
                            id: "artist:" + n,
                            text: n,
                            icon: "artist"
                        }));
                artistPopup.popup(null, at.x, at.y);
            } else if (id.startsWith("artist:"))
                root.app.navigate("collection:" + id, true);
        }
    }

    Menu {
        id: artistPopup

        objectName: "artistMenu"
        host: root.host
        onTriggered: id => root.app.navigate("collection:" + id, true)
    }

    Menu {
        id: playlistPopup

        objectName: "playlistMenu"
        host: root.host
        onTriggered: id => {
            if (id === "new")
                root.app.dialogs.newPlaylist(root._keys);
            else
                music.addToPlaylist(id, root._keys);
        }
    }

    Menu {
        id: collectionPopup

        objectName: "collectionMenu"
        host: root.host
        onTriggered: id => {
            const c = root._summary;
            if (id === "play")
                player.playCollection(c.id, "", false);
            else if (id === "shuffle")
                player.playCollection(c.id, "", true);
            else if (id === "queue")
                player.addToQueue(c.keys);
            else if (id === "rename")
                root.app.dialogs.renamePlaylist(c.id, c.title);
            else if (id === "delete")
                root.app.dialogs.deletePlaylist(c.id, c.title);
            else if (id === "spotify")
                music.openUrl(c.source);
        }
    }

    Menu {
        id: sortPopup

        objectName: "sortMenu"
        host: root.host
        onTriggered: id => root._sortApply && root._sortApply(id)
    }
}
