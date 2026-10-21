pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Configuration files and the backups kept before every saved change.
PageBase {
    id: root

    readonly property var kinds: ({atajos: "Atajos", ajustes: "Ajustes del escritorio", preferencias: "Preferencias", archivo: "Archivo"})
    property var backups: []
    property var files: []
    property string status: ""
    property bool failed: false
    property string armed: ""

    function adopt(data: var): void {
        backups = data.backups;
        files = data.files;
    }

    function load(): void {
        DesktopBridge.call("backups.state", {}, data => adopt(data), message => {
            status = message;
            failed = true;
        });
    }

    function open(path: string): void {
        DesktopBridge.call("file.open", {path: path}, () => {}, message => {
            status = message;
            failed = true;
        });
    }

    function restore(name: string): void {
        // First click arms, second confirms.
        if (armed !== name) {
            armed = name;
            status = "Pulsa de nuevo para restaurar esta copia; la configuración actual también se respalda.";
            failed = false;
            return;
        }
        armed = "";
        DesktopBridge.call("backups.restore", {name: name}, data => {
            root.adopt(data);
            root.status = "Copia restaurada.";
            root.failed = false;
        }, message => {
            root.status = message;
            root.failed = true;
        });
    }

    title: "Archivos y copias"
    isSubPage: true
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: "Configuración (se abre en Neovim)"
        }

        Repeater {
            model: root.files

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: index === root.files.length - 1
                icon: "description"
                text: modelData.title
                subtext: modelData.path
                trailingIcon: "open_in_new"
                onClicked: root.open(modelData.path)
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        SectionHeader {
            text: "Copias disponibles"
        }

        Repeater {
            model: root.backups

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: index === root.backups.length - 1
                icon: modelData.restorable ? "history" : "draft"
                text: root.kinds[modelData.kind] + " · " + modelData.name
                subtext: modelData.restorable ? (root.armed === modelData.name ? "Pulsa de nuevo para confirmar" : "Pulsa para restaurar") : "Pulsa para inspeccionar"
                trailingIcon: modelData.restorable ? "restore" : "open_in_new"
                onClicked: modelData.restorable ? root.restore(modelData.name) : root.open(modelData.path + (modelData.kind === "preferencias" ? "/receipt.json" : ""))
            }
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                type: TextButton.Tonal
                text: "Actualizar"
                onClicked: root.load()
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Abrir carpeta de copias"
                onClicked: Quickshell.execDetached(["xdg-open", Quickshell.env("HOME") + "/.local/share/orbit/settings-backups"])
            }
        }
    }
}
