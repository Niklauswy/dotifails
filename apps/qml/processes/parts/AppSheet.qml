// The sheet a window opens into (inside a ContainerTransform): state shape and icon, name and title, actions, the
// thumbnail in large, rolling CPU/memory/GPU/process figures, a scrub chart and the app's busiest processes.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: sheet

    property var entry: ({})
    readonly property var stat: procs.stats[entry.app] ?? ({})
    readonly property var kids: { procs.stats; return procs.appProcesses(entry.app ?? ""); }
    readonly property color tintColour: (entry.tint ?? "") !== "" ? Qt.color(entry.tint) : Theme.m3primary

    signal closeRequested
    signal showProcesses(string app)

    Row {
        id: head

        x: Theme.padding.large ?? 0
        y: Theme.padding.large ?? 0
        width: parent.width - x * 2
        spacing: Theme.spacing.medium ?? 0

        StateShape {
            state: "G"
            color: Qt.tint(Theme.m3surfaceContainerHighest, Qt.alpha(sheet.tintColour, 0.32))

            AppIcon {
                anchors.centerIn: parent
                source: sheet.entry.icon ?? ""
                tint: sheet.entry.tint ?? ""
                label: sheet.entry.name ?? ""
                color: Qt.alpha(Theme.m3surface, 0)
            }
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - actions.width - parent.spacing

            Label {
                width: parent.width
                text: sheet.entry.name ?? ""
                role: "headline.small"
                elide: Text.ElideRight
            }

            Label {
                width: parent.width
                text: (sheet.entry.title ?? "") + " · espacio " + (sheet.entry.ws ?? "")
                role: "body.medium"
                color: Theme.m3onSurfaceVariant
                elide: Text.ElideRight
            }
        }

        Row {
            id: actions

            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.small ?? 0

            Button {
                type: "filled"
                icon: "open_in_new"
                text: "Ir a la ventana"
                onClicked: procs.focusApp(sheet.entry.app)
            }

            Button {
                type: "tonal"
                icon: "my_location"
                text: "Localizar"
                onClicked: procs.locateApp(sheet.entry.app)
            }

            Button {
                type: "tonal"
                icon: "list"
                text: "Procesos"
                onClicked: sheet.showProcesses(sheet.entry.app)
            }

            Button {
                type: "tonal"
                icon: "cancel"
                text: "Cerrar"
                containerColor: Theme.m3errorContainer
                contentRestColor: Theme.m3onErrorContainer
                onClicked: procs.closeApp(sheet.entry.app, false)
            }

            IconButton {
                icon: "close"
                onClicked: sheet.closeRequested()
            }
        }
    }

    Rectangle {
        id: big

        anchors.top: head.bottom
        anchors.topMargin: Theme.spacing.large ?? 0
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.padding.large ?? 0
        x: Theme.padding.large ?? 0
        width: (parent.width - x * 3) * 0.56
        radius: Theme.rounding.extraLarge ?? 0
        clip: true
        color: Qt.tint(Theme.m3surfaceContainerHigh, Qt.alpha(sheet.tintColour, 0.22))

        Image {
            id: bigThumb

            anchors.fill: parent
            source: sheet.entry.thumb ?? ""
            fillMode: Image.PreserveAspectFit
            cache: true
            visible: status === Image.Ready
        }

        AppIcon {
            anchors.centerIn: parent
            visible: !bigThumb.visible
            source: sheet.entry.icon ?? ""
            tint: sheet.entry.tint ?? ""
            label: sheet.entry.name ?? ""
            size: Metrics.emptyEmblemSize
        }
    }

    Column {
        anchors.top: big.top
        anchors.left: big.right
        anchors.leftMargin: Theme.padding.large ?? 0
        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.large ?? 0
        spacing: Theme.spacing.medium ?? 0

        Row {
            width: parent.width
            spacing: Theme.spacing.small ?? 0

            Repeater {
                model: [["CPU", Fmt.pct(sheet.stat.cpu ?? 0)], ["Memoria", Fmt.mem(sheet.stat.mem ?? 0)], ["GPU", Fmt.pct(sheet.stat.gpu ?? 0)], ["Procesos", String(sheet.stat.count ?? 0)]]

                Rectangle {
                    required property var modelData

                    width: (parent.width - parent.spacing * 3) / 4
                    height: Metrics.listItemThreeLine
                    radius: Theme.rounding.large ?? 0
                    color: Theme.m3surfaceContainerHigh

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        x: Theme.padding.medium ?? 0

                        Label {
                            text: parent.parent.modelData[0]
                            role: "label.medium"
                            color: Theme.m3onSurfaceVariant
                        }

                        RollingNumber {
                            text: parent.parent.modelData[1]
                            role: "title.large"
                        }
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: Metrics.topAppBarLarge
            radius: Theme.rounding.large ?? 0
            color: Theme.m3surfaceContainerHigh

            LiveChart {
                anchors.fill: parent
                anchors.margins: Theme.padding.medium ?? 0
                series: [sheet.stat.history ?? []]
                colors: [Qt.tint(Theme.m3primary, Qt.alpha(sheet.tintColour, 0.6))]
                interval: procs.interval
                scrub: true
                formatValue: v => Fmt.pct(v)
                labelAt: i => {
                    const ago = Math.round(((sheet.stat.history ?? []).length - 1 - i) * procs.interval / 1000);
                    return ago ? "hace " + ago + " s" : "ahora";
                }
            }
        }

        Repeater {
            model: sheet.kids

            Row {
                required property var modelData

                width: parent.width
                height: Metrics.chipHeight
                spacing: Theme.spacing.medium ?? 0

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Theme.spacing.small ?? 0
                    height: width
                    radius: width / 2
                    color: Theme["m3" + Fmt.stateColourRole(parent.modelData.state)]
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width * 0.6
                    text: parent.modelData.name + "  " + parent.modelData.pid
                    role: "body.medium"
                    elide: Text.ElideRight
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Fmt.pct(parent.modelData.cpu) + " · " + Fmt.mem(parent.modelData.mem)
                    role: "label.medium"
                    color: Theme.m3onSurfaceVariant
                }
            }
        }
    }
}
