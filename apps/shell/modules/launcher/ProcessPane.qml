pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.services
import qs.modules.launcher.services

// The launcher's side pane for a running app («En ejecución») or a kill row: its live window, CPU, memory and
// process count rolling every second, a minute of CPU as a sparkline, and the actions with their keys. Close and
// force ask for a second press (the panel's confirmKey), shown here in the error colour.
Item {
    id: root

    property var row: null
    property var panel: null
    readonly property bool isApp: row?.kind === "proc"
    readonly property var entry: DesktopEntries.heuristicLookup(isApp ? row.app : (row?.name ?? ""))
    readonly property var toplevel: {
        if (!isApp)
            return null;
        const want = String(row.address).replace(/^0x/, "");
        return Hypr.toplevels.values.find(t => String(t.address).replace(/^0x/, "") === want) ?? null;
    }
    readonly property var stats: ProcStats.current
    readonly property string confirm: panel?.confirmKey ?? ""

    function mem(bytes) {
        const mb = (bytes || 0) / 1048576;
        return mb >= 1024 ? (mb / 1024).toFixed(1) + " GB" : Math.round(mb) + " MB";
    }

    clip: true

    Column {
        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.medium

        // The window, live.
        StyledRect {
            width: parent.width
            height: width * 0.5
            radius: Tokens.rounding.large
            color: Colours.palette.m3surfaceContainer
            clip: true

            ScreencopyView {
                anchors.fill: parent
                visible: root.toplevel !== null
                captureSource: root.toplevel?.wayland ?? null
                live: root.visible && root.toplevel !== null
            }

            MaterialIcon {
                anchors.centerIn: parent
                visible: root.toplevel === null
                text: root.isApp ? "web_asset" : "memory"
                color: Colours.palette.m3onSurfaceVariant
            }
        }

        Row {
            width: parent.width
            spacing: Tokens.spacing.medium

            StyledRect {
                implicitWidth: Tokens.padding.extraExtraLarge
                implicitHeight: implicitWidth
                radius: Tokens.rounding.large
                color: Colours.palette.m3secondaryContainer

                Image {
                    id: icon

                    anchors.centerIn: parent
                    width: parent.width * 0.66
                    height: width
                    visible: status === Image.Ready
                    source: root.entry?.icon ? Quickshell.iconPath(root.entry.icon, true) : ""
                    sourceSize: Qt.size(width * 2, height * 2)
                }

                MaterialIcon {
                    anchors.centerIn: parent
                    visible: icon.status !== Image.Ready
                    text: "memory"
                    color: Colours.palette.m3onSecondaryContainer
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - x

                StyledText {
                    width: parent.width
                    text: root.isApp ? (root.row?.name ?? "") : (root.row?.name ?? "")
                    font: Tokens.font.title.medium
                    elide: Text.ElideRight
                }

                StyledText {
                    width: parent.width
                    text: root.isApp ? (root.row.windowTitle || "") + (root.row.workspace ? " · espacio " + root.row.workspace : "")
                                     : "Programa sin ventana o proceso suelto"
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.small
                    elide: Text.ElideRight
                }
            }
        }

        Row {
            width: parent.width
            spacing: Tokens.spacing.small

            Repeater {
                model: [["CPU", (root.stats.cpu < 10 ? Number(root.stats.cpu).toFixed(1) : Math.round(root.stats.cpu)) + " %"],
                        ["Memoria", root.mem(root.stats.memory)], ["Procesos", String(root.stats.count)]]

                StyledRect {
                    required property var modelData

                    width: (parent.width - parent.spacing * 2) / 3
                    implicitHeight: figure.implicitHeight + Tokens.padding.medium * 2
                    radius: Tokens.rounding.medium
                    color: Colours.palette.m3surfaceContainer

                    Column {
                        id: figure

                        anchors.verticalCenter: parent.verticalCenter
                        x: Tokens.padding.medium

                        StyledText {
                            text: parent.parent.modelData[0]
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.label.small
                        }

                        StyledText {
                            text: parent.parent.modelData[1]
                            font: Tokens.font.title.medium
                        }
                    }
                }
            }
        }

        // A minute of CPU.
        Canvas {
            id: spark

            width: parent.width
            height: Tokens.padding.extraExtraLarge
            onPaint: {
                const g = getContext("2d");
                g.reset();
                const h = ProcStats.history;
                if (h.length < 2)
                    return;
                const max = Math.max(10, ...h) * 1.2;
                const step = width / 59;
                g.beginPath();
                h.forEach((v, i) => {
                    const x = (i + 60 - h.length) * step, y = height - v / max * height;
                    i ? g.lineTo(x, y) : g.moveTo(x, y);
                });
                g.strokeStyle = Colours.palette.m3primary;
                g.lineWidth = 2;
                g.stroke();
                g.lineTo((59) * step, height);
                g.lineTo((60 - h.length) * step, height);
                g.closePath();
                g.fillStyle = Qt.alpha(Colours.palette.m3primary, 0.18);
                g.fill();
            }

            Connections {
                target: ProcStats

                function onHistoryChanged() {
                    spark.requestPaint();
                }
            }
        }

        Column {
            width: parent.width

            Repeater {
                model: (root.isApp ? [
                    {icon: "open_in_new", text: "Ir a la ventana", keys: "↵"},
                    {icon: "list_alt", text: "Abrir en Processes", keys: "Ctrl ↵"},
                    {icon: "my_location", text: "Localizar en pantalla", keys: "Ctrl L"}
                ] : [
                    {icon: "list_alt", text: "Abrir en Processes", keys: "Ctrl ↵"}
                ]).concat([
                    {icon: "cancel", text: root.confirm === "close:" + (root.row?.key ?? "") ? "Pulsa otra vez para cerrar" : "Cerrar", keys: "Ctrl W", danger: true, armed: root.confirm === "close:" + (root.row?.key ?? "")},
                    {icon: "bolt", text: root.confirm === "force:" + (root.row?.key ?? "") ? "Pulsa otra vez para forzar el cierre" : "Forzar cierre", keys: "Ctrl ⇧ W", danger: true, armed: root.confirm === "force:" + (root.row?.key ?? "")}
                ])

                StyledRect {
                    required property var modelData

                    width: parent.width
                    implicitHeight: actionRow.implicitHeight + Tokens.padding.small * 2
                    radius: Tokens.rounding.medium
                    color: modelData.armed ? Colours.palette.m3errorContainer : "transparent"

                    Row {
                        id: actionRow

                        anchors.verticalCenter: parent.verticalCenter
                        x: Tokens.padding.small
                        width: parent.width - x * 2
                        spacing: Tokens.spacing.medium

                        MaterialIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.parent.modelData.icon
                            color: parent.parent.modelData.danger ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                        }

                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - keyLabel.width - parent.spacing
                            text: parent.parent.modelData.text
                            color: parent.parent.modelData.danger ? Colours.palette.m3error : Colours.palette.m3onSurface
                            font: Tokens.font.body.medium
                            elide: Text.ElideRight
                        }

                        StyledText {
                            id: keyLabel

                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.parent.modelData.keys
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.label.medium
                        }
                    }
                }
            }
        }
    }
}
