// Playlist dialogs: new (suggested «Mi playlist n.º N», optionally with songs), rename, and delete with
// confirmation. Creating an empty playlist opens it; deleting the open one goes back to Inicio.
import QtQuick
import WysunM3

Item {
    id: root

    property var app
    property Item host
    property var _keys: []
    property string _id

    function newPlaylist(keys) {
        _keys = keys || [];
        nameDialog.mode = "new";
        nameDialog.title = "Nueva playlist";
        nameField.text = music.suggestedPlaylistName();
        nameDialog.open();
        nameField.forceFocus();
        nameField.selectAll();
    }

    function renamePlaylist(id, title) {
        _id = id;
        nameDialog.mode = "rename";
        nameDialog.title = "Cambiar nombre";
        nameField.text = title;
        nameDialog.open();
        nameField.forceFocus();
        nameField.selectAll();
    }

    function deletePlaylist(id, title) {
        _id = id;
        deleteDialog.message = "¿Eliminar «" + title + "»? Las canciones siguen en tu biblioteca.";
        deleteDialog.open();
    }

    function _commitName() {
        const name = nameField.text.trim();
        if (nameDialog.mode === "new") {
            const id = music.createPlaylist(name, root._keys);
            if (root._keys.length === 0)
                root.app.navigate("collection:" + id, true);
        } else {
            music.renamePlaylist(root._id, name);
        }
        nameDialog.close();
    }

    Dialog {
        id: nameDialog

        property string mode: "new"

        objectName: "playlistNameDialog"
        host: root.host
        icon: "queue_music"
        actions: [{id: "cancel", text: "Cancelar"}, {id: "ok", text: mode === "new" ? "Crear" : "Guardar", primary: true}]
        onAccepted: id => {
            if (id === "ok")
                root._commitName();
        }

        TextField {
            id: nameField

            objectName: "playlistNameField"
            width: Metrics.textFieldMinWidth * 1.4
            label: "Nombre"
            labelBackground: Theme.m3surfaceContainerHigh
            onAccepted: root._commitName()
        }
    }

    Dialog {
        id: deleteDialog

        objectName: "deletePlaylistDialog"
        host: root.host
        icon: "delete"
        title: "Eliminar playlist"
        actions: [{id: "cancel", text: "Cancelar"}, {id: "delete", text: "Eliminar", primary: true}]
        onAccepted: id => {
            if (id !== "delete")
                return;
            const open = root.app.route === "collection:" + root._id;
            music.deletePlaylist(root._id);
            if (open)
                root.app.navigate("home", true);
        }
    }
}
