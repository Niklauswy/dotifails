pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Add, edit, delete or open one SSH connection in a terminal.
PageBase {
    id: root

    readonly property var row: nState.selectedSsh
    readonly property bool editing: row !== null && row !== undefined
    readonly property bool imported: editing && row.imported
    property string nameText: row?.name ?? ""
    property string hostText: row?.host ?? ""
    property string userText: row?.user ?? ""
    property string portText: String(row?.port ?? 22)
    property string status: imported ? "Esta conexión viene de ~/.ssh/config y no se edita aquí." : ""
    property bool failed: false

    function fail(message: string): void {
        status = message;
        failed = true;
    }

    function save(): void {
        DesktopBridge.call("ssh.save", {name: nameText, host: hostText, user: userText, port: portText, index: editing ? row.index : -1}, () => nState.closeSubPage(), fail);
    }

    function remove(): void {
        DesktopBridge.call("ssh.delete", {index: row.index}, () => nState.closeSubPage(), fail);
    }

    function connect(): void {
        DesktopBridge.call("ssh.connect", {name: row.name}, () => {
            root.status = "Abriendo la conexión en una terminal…";
            root.failed = false;
        }, fail);
    }

    title: editing ? row.name : "Nueva conexión"
    isSubPage: true

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        TextFieldRow {
            first: true
            label: "Nombre"
            value: root.nameText
            maximumLength: 80
            onValueEdited: value => root.nameText = value
        }

        TextFieldRow {
            label: "Host"
            subtext: "Nombre, IPv4 o IPv6"
            value: root.hostText
            maximumLength: 253
            onValueEdited: value => root.hostText = value
        }

        TextFieldRow {
            label: "Usuario"
            subtext: "Opcional"
            value: root.userText
            maximumLength: 64
            onValueEdited: value => root.userText = value
        }

        TextFieldRow {
            last: true
            label: "Puerto"
            value: root.portText
            maximumLength: 5
            smallField: true
            onValueEdited: value => root.portText = value
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                visible: root.editing
                text: "Conectar"
                onClicked: root.connect()
            }

            ActionButton {
                visible: !root.imported
                type: root.editing ? TextButton.Tonal : TextButton.Filled
                text: "Guardar"
                disabled: !root.nameText.trim() || !root.hostText.trim()
                onClicked: root.save()
            }

            ActionButton {
                visible: root.editing && !root.imported
                type: TextButton.Tonal
                text: "Eliminar"
                onClicked: root.remove()
            }
        }
    }
}
