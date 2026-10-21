pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Fixed workspaces 1–10 per screen.
PageBase {
    id: root

    property var rows: []
    property var outputs: []
    property string status: ""
    property bool failed: false
    property string confirmReset: ""

    function adopt(data: var): void {
        rows = data.rows;
        outputs = data.outputs;
    }

    function load(): void {
        DesktopBridge.call("workspaces.state", {}, data => root.adopt(data), message => {
            status = message;
            failed = true;
        });
    }

    function edit(args: var, success: string): void {
        DesktopBridge.call("workspaces.edit", args, data => {
            root.adopt(data);
            root.status = success;
            root.failed = false;
        }, message => {
            root.status = message;
            root.failed = true;
        });
    }

    title: "Escritorios"
    isSubPage: true
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: "Escritorios fijos por pantalla"
        }

        StyledText {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.bottomMargin: Tokens.spacing.small
            wrapMode: Text.Wrap
            text: "Cada número pertenece a una pantalla y se conserva al iniciar la sesión. La barra muestra el 10 como 0, igual que Super+0."
            color: Colours.palette.m3outline
            font: Tokens.font.label.small
        }

        Repeater {
            model: root.rows

            OptionRow {
                id: row

                required property var modelData
                required property int index

                first: index === 0
                last: index === root.rows.length - 1
                label: "Escritorio " + modelData.label
                subtext: modelData.windows + (modelData.windows === 1 ? " ventana" : " ventanas") + (modelData.active ? " · visible" : "") + (modelData.fixed ? "" : " · no fijo")
                visible: true
                options: root.outputs.map(o => ({value: o, label: o}))
                current: modelData.assigned || modelData.monitor
                onPicked: value => {
                    if (modelData.number)
                        root.edit({action: "assign", number: modelData.number, monitor: value}, "Escritorio " + modelData.label + " movido a " + value + ".");
                    else
                        root.status = "Ese escritorio no es numérico; no forma parte de la distribución fija.";
                }
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        SectionHeader {
            text: "Asignar o quitar"
        }

        Repeater {
            model: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].filter(n => !root.rows.some(r => r.number === n))

            OptionRow {
                id: free

                required property int modelData
                required property int index

                first: index === 0
                last: index === 0 && false
                label: "Asignar escritorio " + (modelData === 10 ? "0" : modelData)
                subtext: "Elige la pantalla donde se abrirá"
                options: root.outputs.map(o => ({value: o, label: o}))
                current: ""
                fallbackText: "Pantalla…"
                onPicked: value => root.edit({action: "assign", number: free.modelData, monitor: value}, "Escritorio " + (free.modelData === 10 ? "0" : free.modelData) + " asignado a " + value + ".")
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
                text: root.confirmReset ? "Confirmar restablecer" : "Restablecer 1–5 / 6–9 / 0"
                onClicked: {
                    if (root.confirmReset) {
                        root.confirmReset = "";
                        root.edit({action: "reset"}, "Distribución automática restablecida.");
                    } else {
                        root.confirmReset = "yes";
                        resetTimer.restart();
                    }
                }
            }
        }

        Repeater {
            model: root.rows.filter(r => r.fixed && r.number && r.windows === 0)

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: false
                icon: "delete"
                text: "Quitar escritorio " + modelData.label + " (vacío)"
                subtext: "Deja de formar parte de la distribución fija"
                onClicked: root.edit({action: "remove", number: modelData.number}, "Escritorio " + modelData.label + " quitado.")
            }
        }

        Timer {
            id: resetTimer

            interval: 5000
            onTriggered: root.confirmReset = ""
        }
    }
}
