// The menus of Wysun Files in window coordinates (F-31, F-32): the context menu of the selection (or of the
// folder when nothing is under the pointer), «Nuevo» (folder, empty file) and «Más acciones». Entries are disabled
// as in the Widgets UI (nothing to paste, an operation running, more than one file to rename…).
import QtQuick
import WysunM3

Item {
    id: root

    property var app                        // the window: tab, model, keyAction()
    property Item host
    property var _paths: []

    function context(paths, x, y) {
        _paths = paths || [];
        const one = _paths.length === 1;
        const any = _paths.length > 0;
        const idle = !fileOps.busy;
        const folder = one && app.model.get(app.model.rowOf(_paths[0])).isDir === true;
        const entries = [];
        if (any) {
            entries.push({id: "open", text: "Abrir", icon: "open_in_new", shortcut: "Enter"});
            entries.push({id: "tab", text: "Abrir en nueva pestaña", icon: "tab", disabled: !folder});
            entries.push({id: "preview", text: "Vista previa ampliada", icon: "visibility", shortcut: "Espacio", disabled: !one || folder});
            entries.push({divider: true});
            entries.push({id: "copy", text: "Copiar", icon: "content_copy", shortcut: "Ctrl+C"});
            entries.push({id: "cut", text: "Cortar", icon: "content_cut", shortcut: "Ctrl+X", disabled: !idle});
        }
        entries.push({id: "paste", text: "Pegar aquí", icon: "content_paste", shortcut: "Ctrl+V", disabled: !fileOps.canPaste || !idle});
        if (any) {
            entries.push({divider: true});
            entries.push({id: "rename", text: "Cambiar nombre…", icon: "drive_file_rename_outline", shortcut: "F2", disabled: !one || !idle});
            entries.push({id: "trash", text: "Enviar a la papelera", icon: "delete", shortcut: "Supr", disabled: !idle});
        }
        entries.push({divider: true});
        entries.push({id: "copyPath", text: "Copiar ruta", icon: "link", shortcut: "Ctrl+Shift+C"});
        entries.push({id: "newFolder", text: "Nueva carpeta", icon: "create_new_folder", shortcut: "Ctrl+Shift+N", disabled: !idle});
        entries.push({id: "terminal", text: "Terminal aquí", icon: "terminal"});
        entries.push({id: "properties", text: "Propiedades", icon: "info", disabled: _paths.length > 1});
        contextMenu.model = entries;
        contextMenu.popup(null, x, y);
    }

    function newMenu(x, y) {
        createMenu.popup(null, x, y);
    }

    function more(x, y) {
        const marked = places.isBookmark(app.tab.path);
        moreMenu.model = [{id: "newTab", text: "Nueva pestaña", icon: "tab", shortcut: "Ctrl+T"}, {id: "up", text: "Carpeta superior", icon: "arrow_upward", shortcut: "Alt+↑", disabled: !app.tab.canUp}, {id: "bookmark", text: marked ? "Quitar de marcadores" : "Añadir a marcadores", icon: marked ? "bookmark_remove" : "bookmark_add"}, {divider: true}, {id: "terminal", text: "Terminal aquí", icon: "terminal"}, {id: "hidden", text: files.showHidden ? "Ocultar archivos ocultos" : "Mostrar archivos ocultos", icon: files.showHidden ? "visibility_off" : "visibility", shortcut: "Ctrl+H"}, {id: "copyPath", text: "Copiar ruta", icon: "link", shortcut: "Ctrl+Shift+C"}, {id: "properties", text: "Propiedades", icon: "info"}];
        moreMenu.popup(null, x, y);
    }

    function run(id) {
        const folder = app.tab.path;
        switch (id) {
        case "open":
            app.openPaths(_paths);
            break;
        case "tab":
            files.newTab(_paths[0]);
            break;
        case "preview":
            app.keyAction("preview");
            break;
        case "terminal":
            fileOps.terminal(folder);
            break;
        case "copyPath":
            files.copyText(_paths.length === 1 ? _paths[0] : folder);
            app.snackbarHost.show({text: "Ruta copiada"});
            break;
        case "properties":
            app.dialogs.properties(_paths.length === 1 ? _paths[0] : folder);
            break;
        case "newTab":
            files.newTab("");
            break;
        case "up":
            app.tab.up();
            break;
        case "bookmark":
            app.snackbarHost.show({text: places.toggleBookmark(folder) ? "Carpeta añadida a marcadores" : "Carpeta quitada de marcadores"});
            break;
        case "hidden":
            files.setShowHidden(!files.showHidden);
            break;
        default:
            app.keyAction(id, _paths);
        }
    }

    Menu {
        id: contextMenu

        objectName: "contextMenu"
        host: root.host
        onTriggered: id => root.run(id)
    }

    Menu {
        id: createMenu

        objectName: "newMenu"
        host: root.host
        model: [{id: "newFolder", text: "Carpeta", icon: "create_new_folder", shortcut: "Ctrl+Shift+N"}, {id: "newFile", text: "Archivo vacío", icon: "note_add"}]
        onTriggered: id => root.app.keyAction(id)
    }

    Menu {
        id: moreMenu

        objectName: "moreMenu"
        host: root.host
        onTriggered: id => {
            root._paths = [];
            root.run(id);
        }
    }
}
