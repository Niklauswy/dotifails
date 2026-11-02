// The dialogs of Wysun Files (files-dialogs.html): a name (new folder, new file, rename) with the error under the
// field and the stem preselected, the trash confirmation with the count, and the properties of a file or folder.
// Nothing is written until Python's operation runs; a name that is taken is refused there, never overwritten.
import QtQuick
import WysunM3

Item {
    id: root

    property var app
    property Item host

    // mode: newFolder | newFile | rename
    function askName(mode, folder, path) {
        nameDialog.mode = mode;
        nameDialog.folder = folder;
        nameDialog.path = path || "";
        const base = path ? path.slice(path.lastIndexOf("/") + 1) : fileOps.freeName(folder, mode === "newFolder" ? "Carpeta nueva" : "Sin título.txt");
        field.text = base;
        field.error = false;
        field.errorText = "";
        nameDialog.open();
        selectStem();
    }

    function selectedName() {
        return field.input.selectedText;
    }

    function selectStem() {
        field.input.forceActiveFocus();
        const dot = field.text.lastIndexOf(".");
        if (nameDialog.mode !== "newFolder" && dot > 0)
            field.input.select(0, dot);
        else
            field.input.selectAll();
    }

    function commitName() {
        const name = field.text;
        const problem = fileOps.validateName(name);
        if (problem !== "") {
            field.error = true;
            field.errorText = problem;
            nameDialog.open();                  // an action closed it: stay until the name is valid
            field.input.forceActiveFocus();
            return;
        }
        if (nameDialog.mode === "newFolder")
            fileOps.mkdir(nameDialog.folder, name);
        else if (nameDialog.mode === "newFile")
            fileOps.newFile(nameDialog.folder, name);
        else
            fileOps.rename(nameDialog.path, name);
    }

    function confirmTrash(paths) {
        if (!paths || paths.length === 0)
            return;
        trashDialog.paths = paths;
        const names = paths.map(p => "«" + p.slice(p.lastIndexOf("/") + 1) + "»");
        trashDialog.title = paths.length === 1 ? "¿Enviar " + names[0] + " a la papelera?" : "¿Enviar " + paths.length + " elementos a la papelera?";
        trashDialog.message = (paths.length > 1 && paths.length <= 3 ? names.join(", ") + ". " : "") + "Podrás recuperarlos desde la Papelera.";
        trashDialog.open();
    }

    // «Compartir en la red»: what Wysun LANShare needs to know; uploads only for one folder, both off by default.
    function share(paths, oneFolder) {
        if (!paths || paths.length === 0)
            return;
        shareDialog.paths = paths;
        shareDialog.oneFolder = oneFolder === true;
        const name = paths[0].slice(paths[0].lastIndexOf("/") + 1) || paths[0];
        shareDialog.title = paths.length === 1 ? "Compartir «" + name + "» en la red" : "Compartir " + paths.length + " elementos en la red";
        uploadsChip.selected = false;
        passwordChip.selected = false;
        shareDialog.open();
    }

    function properties(path) {
        propertiesDialog.info = fileOps.properties(path);
        propertiesDialog.open();
    }

    Dialog {
        id: nameDialog

        property string mode: "newFolder"
        property string folder
        property string path

        objectName: "nameDialog"
        host: root.host
        icon: mode === "newFolder" ? "create_new_folder" : mode === "newFile" ? "note_add" : ""
        title: mode === "newFolder" ? "Nueva carpeta" : mode === "newFile" ? "Archivo nuevo" : "Cambiar nombre"
        actions: [{id: "cancel", text: "Cancelar"}, {id: "ok", text: mode === "rename" ? "Cambiar nombre" : "Crear", primary: true}]
        onAccepted: id => {
            if (id === "ok")
                root.commitName();
        }

        TextField {
            id: field

            objectName: "nameField"
            width: Metrics.dialogMinWidth + Metrics.textFieldMinWidth / 2
            label: "Nombre"
            labelBackground: Theme.m3surfaceContainerHigh
            onTextChanged: if (error) {
                error = fileOps.validateName(text) !== "";
                errorText = error ? fileOps.validateName(text) : "";
            }
            input.Keys.onReturnPressed: {
                nameDialog.close();
                root.commitName();
            }
            input.Keys.onEnterPressed: {
                nameDialog.close();
                root.commitName();
            }
        }
    }

    Dialog {
        id: trashDialog

        property var paths: []

        objectName: "trashDialog"
        host: root.host
        icon: "delete"
        actions: [{id: "cancel", text: "Cancelar"}, {id: "trash", text: "Enviar a la papelera", primary: true}]
        onAccepted: id => {
            if (id === "trash")
                fileOps.trash(paths);
        }
    }

    Dialog {
        id: shareDialog

        property var paths: []
        property bool oneFolder

        objectName: "shareDialog"
        host: root.host
        icon: "share"
        message: "Cualquiera en esta red podrá verlo y descargarlo desde el navegador. La dirección aparece en la barra, que también sirve para dejar de compartir."
        actions: [{id: "cancel", text: "Cancelar"}, {id: "share", text: "Compartir", primary: true}]
        onAccepted: id => {
            if (id !== "share")
                return;
            if (fileOps.shareOnNetwork(paths, oneFolder && uploadsChip.selected, passwordChip.selected))
                root.app.snackbarHost.show({text: passwordChip.selected ? "Compartiendo en la red · la dirección y la contraseña están en la barra" : "Compartiendo en la red · la dirección está en la barra"});
        }

        Flow {
            width: Metrics.dialogMinWidth + Metrics.textFieldMinWidth / 2
            spacing: Theme.spacing.small ?? 0

            Chip {
                id: uploadsChip

                objectName: "shareUploads"
                visible: shareDialog.oneFolder
                kind: "filter"
                icon: "upload"
                text: "Permitir subidas"
            }
            Chip {
                id: passwordChip

                objectName: "sharePassword"
                kind: "filter"
                icon: "key"
                text: "Pedir contraseña"
            }
        }
    }

    Dialog {
        id: propertiesDialog

        property var info: ({})

        objectName: "propertiesDialog"
        host: root.host
        actions: [{id: "copy", text: "Copiar ruta"}, {id: "close", text: "Cerrar", primary: true}]
        onAccepted: id => {
            if (id === "copy") {
                files.copyText(info.path ?? "");
                root.app.snackbarHost.show({text: "Ruta copiada"});
            }
        }

        Column {
            spacing: Theme.spacing.large ?? 0
            width: Metrics.dialogMinWidth + Metrics.textFieldMinWidth / 2

            Row {
                spacing: Theme.spacing.large ?? 0

                FileIcon {
                    width: Metrics.listImageSize
                    height: Metrics.listImageSize
                    kind: propertiesDialog.info.kind ?? "other"
                    icon: propertiesDialog.info.icon ?? "draft"
                    badge: propertiesDialog.info.badge ?? ""
                    role: propertiesDialog.info.role ?? "primary"
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacing.extraSmall ?? 0

                    Label {
                        objectName: "propertiesName"
                        role: "title.large"
                        text: propertiesDialog.info.name ?? ""
                        color: Theme.m3onSurface
                        width: Math.min(implicitWidth, Metrics.dialogMinWidth)
                        elide: Text.ElideMiddle
                    }
                    Label {
                        role: "body.medium"
                        text: propertiesDialog.info.error ?? propertiesDialog.info.subtitle ?? ""
                        color: Theme.m3onSurfaceVariant
                    }
                }
            }
            Grid {
                objectName: "propertiesRows"
                columns: 2
                columnSpacing: Theme.spacing.large ?? 0
                rowSpacing: Theme.spacing.small ?? 0

                Repeater {
                    model: (propertiesDialog.info.rows ?? []).reduce((all, row) => all.concat([{text: row.label, label: true}, {text: row.value}]), [])

                    Label {
                        required property var modelData

                        role: "body.medium"
                        text: modelData.text
                        color: modelData.label ? Theme.m3onSurfaceVariant : Theme.m3onSurface
                        width: modelData.label ? implicitWidth : Math.min(implicitWidth, Metrics.dialogMinWidth)
                        wrapMode: modelData.label ? Text.NoWrap : Text.WrapAnywhere
                    }
                }
            }
        }
    }
}
