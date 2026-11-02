// The inspector at the side of the folder (F-50…F-55): surfaceContainerLow with the extraLarge corner. The preview takes
// all the height the information below leaves it; the information sits at the bottom: the name, label/value pairs (a
// click on «Ruta» copies the whole path, file name included) and «Abrir», which opens the file in its app.
import QtQuick
import WysunM3

Rectangle {
    id: root

    property var player
    property alias pane: pane
    readonly property bool showingSource: pane.showSource
    signal openRequested
    signal linkActivated(string target)

    objectName: "inspector"
    radius: Theme.rounding.extraLarge ?? 0
    color: Theme.m3surfaceContainerLow
    clip: true

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: info.top
        anchors.margins: Theme.padding.large ?? 0
        anchors.bottomMargin: Theme.spacing.medium ?? 0
        radius: Theme.rounding.large ?? 0
        color: pane.textual ? Theme.m3surfaceContainerHigh : "transparent"

        PreviewPane {
            id: pane

            anchors.fill: parent
            anchors.margins: pane.textual ? (Theme.padding.medium ?? 0) : 0
            player: root.player
            onLinkActivated: target => root.linkActivated(target)
        }
    }

    Column {
        id: info

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.padding.large ?? 0
        spacing: Theme.spacing.medium ?? 0

        Label {
            objectName: "inspectorName"
            width: parent.width
            role: "title.large"
            text: preview.name
            color: Theme.m3onSurface
            elide: Text.ElideMiddle
        }
        Column {
            objectName: "inspectorMeta"
            width: parent.width
            spacing: Theme.spacing.extraSmall ?? 0

            Repeater {
                model: preview.meta

                Item {
                    id: row

                    required property var modelData
                    readonly property bool isPath: modelData.label === "Ruta"

                    objectName: isPath ? "pathRow" : ""
                    width: parent.width
                    height: Math.max(rowValue.implicitHeight, rowLabel.implicitHeight) + (isPath ? 2 * (Theme.spacing.extraSmall ?? 0) : 0)

                    Label {
                        id: rowLabel

                        anchors.verticalCenter: parent.verticalCenter
                        width: Metrics.listImageSize * 1.6
                        role: "body.small"
                        text: row.modelData.label
                        color: Theme.m3onSurfaceVariant
                    }
                    Label {
                        id: rowValue

                        anchors.left: rowLabel.right
                        anchors.right: copyIcon.visible ? copyIcon.left : parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        role: "body.small"
                        text: row.modelData.value
                        color: Theme.m3onSurface
                        elide: Text.ElideMiddle
                    }
                    Icon {
                        id: copyIcon

                        visible: row.isPath
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        name: "content_copy"
                        size: Metrics.chipIconSize
                        color: Theme.m3onSurfaceVariant
                    }
                    StateLayer {
                        visible: row.isPath
                        anchors.fill: parent
                        radius: Theme.rounding.small ?? 0
                        onClicked: {
                            files.copyText(row.modelData.value);
                            Window.window.snackbarHost.show({text: "Ruta copiada"});
                        }

                        Tooltip {
                            text: "Copiar la ruta"
                        }
                    }
                }
            }
        }
        Flow {
            visible: preview.kind === "markdown"
            width: parent.width
            spacing: Theme.spacing.small ?? 0

            Chip {
                kind: "filter"
                text: "Vista"
                selected: !pane.showSource
                onClicked: {
                    pane.showSource = false;
                    selected = Qt.binding(() => !pane.showSource);
                }
            }
            Chip {
                objectName: "sourceChip"
                kind: "filter"
                text: "Fuente"
                selected: pane.showSource
                onClicked: {
                    pane.showSource = true;
                    selected = Qt.binding(() => pane.showSource);
                }
            }
        }
        Button {
            objectName: "openButton"
            visible: preview.mode !== "none"
            width: parent.width
            type: "filled"
            text: "Abrir"
            onClicked: root.openRequested()
        }
    }
}
