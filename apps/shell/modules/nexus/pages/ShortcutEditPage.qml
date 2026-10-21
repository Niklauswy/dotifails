pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Create or edit one global shortcut. The previous file is kept as a backup.
PageBase {
    id: root

    readonly property var row: nState.selectedShortcut
    readonly property bool editing: row !== null && row !== undefined
    property string keyText: row?.key ?? ""
    property string commandText: row?.command ?? ""
    property string titleText: row?.title ?? ""
    property bool recording: false
    property string status: "Usa «Súper», «Ctrl», «Alt» y «Shift» unidos con «+», por ejemplo Super + Shift + T."
    property bool failed: false

    function submit(group: bool): void {
        DesktopBridge.call("shortcuts.save", {
            key: keyText.trim(),
            command: commandText.trim(),
            title: titleText.trim(),
            source_index: editing ? row.source_index : null,
            part: editing ? row.part : null,
            group: group
        }, () => nState.closeSubPage(), message => {
            root.status = message;
            root.failed = true;
        });
    }

    function remove(): void {
        DesktopBridge.call("shortcuts.delete", {source_index: row.source_index, part: row.part}, () => nState.closeSubPage(), message => {
            root.status = message;
            root.failed = true;
        });
    }

    title: editing ? "Editar atajo" : "Nuevo atajo"
    isSubPage: true

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        TextFieldRow {
            first: true
            label: "Nombre"
            value: root.titleText
            maximumLength: 120
            onValueEdited: value => root.titleText = value
        }

        TextFieldRow {
            label: "Combinación"
            subtext: root.recording ? "Pulsa la combinación…" : ""
            value: root.keyText
            maximumLength: 120
            onValueEdited: value => root.keyText = value
        }

        TextFieldRow {
            last: true
            label: "Comando"
            subtext: "Una sola línea; las llaves {a,b} editan un grupo"
            value: root.commandText
            onValueEdited: value => root.commandText = value
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Guardar atajo"
                disabled: !root.keyText.trim() || !root.commandText.trim()
                onClicked: root.submit(false)
            }

            ActionButton {
                type: TextButton.Tonal
                text: root.recording ? "Cancelar captura" : "Grabar combinación"
                onClicked: {
                    root.recording = !root.recording;
                    root.failed = false;
                    if (root.recording) {
                        capture.forceActiveFocus();
                        root.status = "Pulsa la combinación que quieres usar.";
                    }
                }
            }

            ActionButton {
                visible: root.editing && root.row?.part !== null
                type: TextButton.Tonal
                text: "Editar grupo"
                disabled: !root.keyText.trim() || !root.commandText.trim()
                onClicked: root.submit(true)
            }

            ActionButton {
                visible: root.editing
                type: TextButton.Tonal
                text: "Eliminar"
                onClicked: root.remove()
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Cancelar"
                onClicked: root.nState.closeSubPage()
            }
        }

        // Capture a combination: modifiers plus one key, like the old recorder.
        Item {
            id: capture

            focus: root.recording
            Keys.onPressed: event => {
                if (!root.recording)
                    return;
                const mods = [];
                if (event.modifiers & Qt.MetaModifier) mods.push("Super");
                if (event.modifiers & Qt.ControlModifier) mods.push("Ctrl");
                if (event.modifiers & Qt.AltModifier) mods.push("Alt");
                if (event.modifiers & Qt.ShiftModifier) mods.push("Shift");
                if ([Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R, Qt.Key_AltGr].includes(event.key))
                    return;
                if (event.key === Qt.Key_Escape && mods.length === 0) {
                    root.recording = false;
                    root.status = "Captura cancelada.";
                    return;
                }
                const name = event.text && event.text.trim() && /^[A-Za-z0-9]$/.test(event.text) ? event.text.toUpperCase() : (event.key >= Qt.Key_F1 && event.key <= Qt.Key_F12 ? "F" + (event.key - Qt.Key_F1 + 1) : "");
                if (!name || mods.length === 0) {
                    root.status = "Usa al menos un modificador y una letra, número o tecla F.";
                    root.failed = true;
                    return;
                }
                root.keyText = mods.concat([name]).join(" + ");
                root.recording = false;
                root.failed = false;
                root.status = "Combinación capturada: " + root.keyText;
                event.accepted = true;
            }
        }
    }
}
