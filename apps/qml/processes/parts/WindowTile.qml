// A window in Apps: its live thumbnail (from the shell; a drawn preview in the app's tint when there is none),
// icon, name and title, CPU and memory. Hovering or selecting reveals Abrir, Localizar and Cerrar.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Rectangle {
    id: tile

    property var entry: ({})
    property var stat: ({})
    property bool selected
    readonly property color tintColour: (entry.tint ?? "") !== "" ? Qt.color(entry.tint) : Theme.m3secondary
    readonly property bool reveal: hover.hovered || selected

    signal clicked
    signal locate
    signal closeApp

    height: Metrics.drawerWidth * 0.82
    radius: hover.hovered ? Theme.rounding.large ?? 0 : Theme.rounding.extraLarge ?? 0
    color: selected ? Theme.m3surfaceContainer : Theme.m3surfaceContainerLow
    border.width: selected ? Metrics.focusRingWidth : 0
    border.color: Theme.m3primary

    Behavior on radius {
        Anim {
            kind: "fastSpatial"
        }
    }

    HoverHandler {
        id: hover
    }

    TapHandler {
        onTapped: tile.clicked()
    }

    Rectangle {
        id: preview

        x: Theme.spacing.small ?? 0
        y: Theme.spacing.small ?? 0
        width: parent.width - x * 2
        height: parent.height * 0.56
        radius: Theme.rounding.large ?? 0
        clip: true
        color: Qt.tint(Theme.m3surfaceContainerHigh, Qt.alpha(tile.tintColour, 0.24))

        Image {
            id: thumb

            anchors.fill: parent
            source: tile.entry.thumb ?? ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: false
            visible: status === Image.Ready
        }

        // A drawn stand-in while there is no thumbnail.
        Item {
            anchors.fill: parent
            visible: !thumb.visible

            Repeater {
                model: 4

                Rectangle {
                    required property int index

                    x: Theme.padding.medium ?? 0
                    y: (Theme.padding.medium ?? 0) + index * parent.height * 0.2
                    width: parent.width * [0.8, 0.55, 0.65, 0.3][index]
                    height: parent.height * 0.1
                    radius: height / 2
                    color: Qt.alpha(Qt.tint(Theme.m3onSurface, Qt.alpha(tile.tintColour, 0.5)), 0.14)
                }
            }

            AppIcon {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Theme.padding.medium ?? 0
                source: tile.entry.icon ?? ""
                tint: tile.entry.tint ?? ""
                label: tile.entry.name ?? ""
                size: Metrics.iconButtonSize
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.alpha(Theme.m3surface, 0.55)
            opacity: tile.reveal ? 1 : 0

            Behavior on opacity {
                Anim {
                    kind: "fastEffects"
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: Theme.spacing.small ?? 0

                Button {
                    type: "filled"
                    icon: "open_in_full"
                    text: "Abrir"
                    onClicked: tile.clicked()
                }

                IconButton {
                    type: "tonal"
                    icon: "my_location"
                    onClicked: tile.locate()
                }

                IconButton {
                    type: "tonal"
                    icon: "close"
                    onClicked: tile.closeApp()
                }
            }
        }
    }

    Column {
        anchors.top: preview.bottom
        anchors.topMargin: Theme.spacing.medium ?? 0
        x: Theme.padding.large ?? 0
        width: parent.width - x * 2
        spacing: Theme.spacing.small ?? 0

        Row {
            width: parent.width
            spacing: Theme.spacing.medium ?? 0

            AppIcon {
                source: tile.entry.icon ?? ""
                tint: tile.entry.tint ?? ""
                label: tile.entry.name ?? ""
                size: Metrics.chipHeight
            }

            Column {
                width: parent.width - x

                Label {
                    width: parent.width
                    text: tile.entry.name ?? ""
                    role: "title.small"
                    elide: Text.ElideRight
                }

                Label {
                    width: parent.width
                    text: tile.entry.title ?? ""
                    role: "label.small"
                    color: Theme.m3onSurfaceVariant
                    elide: Text.ElideRight
                }
            }
        }

        Row {
            width: parent.width
            spacing: Theme.spacing.medium ?? 0

            Repeater {
                model: [["CPU " + Fmt.pct(tile.stat.cpu ?? 0), Math.min(1, (tile.stat.cpu ?? 0) / 40), Theme.m3primary],
                        ["Memoria " + Fmt.mem(tile.stat.mem ?? 0), Math.min(1, (tile.stat.mem ?? 0) / 3221225472), Theme.m3tertiary]]

                Column {
                    required property var modelData

                    width: (parent.width - parent.spacing) / 2
                    spacing: Theme.spacing.extraSmall ?? 0

                    Label {
                        text: parent.modelData[0]
                        role: "label.small"
                        color: Theme.m3onSurfaceVariant
                    }

                    Rectangle {
                        width: parent.width
                        height: Metrics.progressThickness
                        radius: height / 2
                        color: Theme.m3surfaceContainerHighest

                        Rectangle {
                            height: parent.height
                            radius: height / 2
                            width: parent.width * parent.parent.modelData[1]
                            color: parent.parent.modelData[2]

                            Behavior on width {
                                Anim {
                                    kind: "defaultSpatial"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
