// A window as a row of the Apps section: a medium 16:9 live thumbnail from the shell (a drawn preview in the app's
// tint while there is none), its name (from the window's desktop entry), the full title, CPU and memory and a thin
// usage bar. Hovering or selecting shows Abrir and Cerrar as icon buttons.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: row

    property var entry: ({})
    property var stat: ({})
    property bool selected
    property real referenceMem: 1
    property int columnIndex: 0
    property int rowIndex: 0
    property var host: null
    readonly property color tintColour: (entry.tint ?? "") !== "" ? Qt.color(entry.tint) : Theme.m3secondary
    readonly property bool reveal: hover.hovered || selected
    // 160 px at the tokens' scale: enough to recognise the window without taking the row's reading width. The page
    // owns the measure (and derives the capture size from it).
    readonly property real thumbWidth: row.host && row.host.rowThumbWidth > 0
        ? row.host.rowThumbWidth : Theme.spacing.extraExtraLarge * 3 + Theme.spacing.large
    readonly property real thumbHeight: thumbWidth * 9 / 16
    readonly property real pad: Theme.spacing.small ?? 0
    readonly property real fraction: {
        const cpu = Math.max(0, stat.cpu ?? 0) / 100;
        const mem = referenceMem > 0 ? (stat.mem ?? 0) / referenceMem : 0;
        return Math.max(0, Math.min(1, Math.max(cpu, mem)));
    }

    signal clicked
    signal closeApp

    implicitHeight: thumbHeight + pad * 2
    height: implicitHeight

    Component.onCompleted: {
        if (host)
            host.registerTile(entry.address ?? "", row);
    }
    Component.onDestruction: {
        if (host)
            host.unregisterTile(entry.address ?? "");
    }

    HoverHandler {
        id: hover
    }

    TapHandler {
        onTapped: row.clicked()
    }

    Rectangle {
        id: surface

        anchors.fill: parent
        radius: selected ? Theme.rounding.medium ?? 0 : Theme.rounding.large ?? 0
        color: row.reveal ? Theme.m3surfaceContainerHigh : Theme.m3surfaceContainer
        border.width: selected ? Metrics.textFieldFocusWidth : 0
        border.color: Theme.m3primary

        Behavior on radius {
            Anim {
                kind: "fastSpatial"
            }
        }

        Behavior on color {
            Anim {
                kind: "fastEffects"
            }
        }
    }

    Item {
        anchors.fill: parent
        anchors.margins: row.pad

        Row {
            id: content

            anchors.fill: parent
            spacing: Theme.spacing.medium ?? 0

            Rectangle {
                id: thumbBox

                width: row.thumbWidth
                height: row.thumbHeight
                radius: Theme.rounding.medium ?? 0
                clip: true
                color: Qt.tint(Theme.m3surfaceContainerHigh, Qt.alpha(row.tintColour, 0.24))

                Image {
                    id: thumb

                    anchors.fill: parent
                    source: row.entry.thumb ?? ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
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
                            y: (Theme.padding.medium ?? 0) + index * parent.height * 0.19
                            width: parent.width * [0.78, 0.52, 0.64, 0.3][index]
                            height: Math.max(Metrics.outlineWidth, parent.height * 0.08)
                            radius: height / 2
                            color: Qt.alpha(Qt.tint(Theme.m3onSurface, Qt.alpha(row.tintColour, 0.5)), 0.16)
                        }
                    }

                    AppIcon {
                        anchors.centerIn: parent
                        source: row.entry.icon ?? ""
                        tint: row.entry.tint ?? ""
                        label: row.entry.name ?? ""
                        size: Metrics.iconButtonSize
                    }
                }
            }

            Column {
                id: info

                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(0, content.width - thumbBox.width - content.spacing)
                spacing: Theme.spacing.extraSmall ?? 0

                Label {
                    width: parent.width
                    text: row.entry.name ?? ""
                    role: "title.small"
                    elide: Text.ElideRight
                }

                Label {
                    width: parent.width
                    text: row.entry.title ?? ""
                    role: "body.small"
                    color: Theme.m3onSurfaceVariant
                    elide: Text.ElideRight
                }

                Label {
                    width: parent.width
                    text: "CPU " + Fmt.pct(row.stat.cpu ?? 0) + " · " + Fmt.mem(row.stat.mem ?? 0)
                    role: "label.small"
                    color: Theme.m3onSurfaceVariant
                    font.features: ({ "tnum": 1 })
                }

                Rectangle {
                    width: parent.width
                    height: Metrics.progressThickness
                    radius: height / 2
                    color: Theme.m3surfaceContainerHighest

                    Rectangle {
                        width: parent.width * row.fraction
                        height: parent.height
                        radius: height / 2
                        color: Theme.m3primary

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

    Rectangle {
        id: actions

        anchors.right: parent.right
        anchors.rightMargin: Theme.spacing.small ?? 0
        anchors.verticalCenter: parent.verticalCenter
        width: actionsRow.implicitWidth + (Theme.spacing.small ?? 0) * 2
        height: Metrics.iconButtonSize + (Theme.spacing.small ?? 0)
        radius: height / 2
        color: Theme.m3surfaceContainerHighest
        opacity: row.reveal ? 1 : 0
        visible: opacity > 0
        z: 2

        Behavior on opacity {
            Anim {
                kind: "fastEffects"
            }
        }

        Row {
            id: actionsRow

            anchors.centerIn: parent
            spacing: Theme.spacing.extraSmall ?? 0

            IconButton {
                icon: "open_in_full"
                onClicked: row.clicked()
            }

            IconButton {
                icon: "close"
                onClicked: row.closeApp()
            }
        }
    }
}
