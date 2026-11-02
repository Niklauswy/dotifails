// The inspector at the side of the folder (F-50…F-55, files-details.html): surfaceContainerLow with the extraLarge
// corner; the preview, the name, label/value pairs and the actions of each kind (Ampliar and Copiar ruta; Vista ⇄
// Fuente for Markdown; play and «Seguir en Wysun Player» for media).
import QtQuick
import QtMultimedia
import WysunM3

Rectangle {
    id: root

    property var player
    property alias pane: pane
    readonly property bool showingSource: pane.showSource
    signal expandRequested
    signal linkActivated(string target)

    objectName: "inspector"
    radius: Theme.rounding.extraLarge ?? 0
    color: Theme.m3surfaceContainerLow

    Flickable {
        anchors.fill: parent
        anchors.margins: Theme.padding.large ?? 0
        contentHeight: column.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: column

            width: parent.width
            spacing: Theme.spacing.medium ?? 0

            Rectangle {
                width: parent.width
                height: pane.textual ? Math.min(parent.width * 1.2, root.height * 0.55) : parent.width * 0.75
                radius: Theme.rounding.large ?? 0
                color: pane.textual ? Theme.m3surfaceContainerHigh : "transparent"
                clip: true

                PreviewPane {
                    id: pane

                    anchors.fill: parent
                    anchors.margins: pane.textual ? (Theme.padding.medium ?? 0) : 0
                    player: root.player
                    onLinkActivated: target => root.linkActivated(target)
                }
            }
            Label {
                objectName: "inspectorName"
                width: parent.width
                role: "title.large"
                text: preview.name
                color: Theme.m3onSurface
                elide: Text.ElideMiddle
            }
            Grid {
                objectName: "inspectorMeta"
                columns: 2
                columnSpacing: Theme.spacing.large ?? 0
                rowSpacing: Theme.spacing.small ?? 0

                Repeater {
                    model: preview.meta.reduce((all, row) => all.concat([{text: row.label, label: true}, {text: row.value}]), [])

                    Label {
                        required property var modelData

                        role: "body.small"
                        text: modelData.text
                        color: modelData.label ? Theme.m3onSurfaceVariant : Theme.m3onSurface
                        width: modelData.label ? implicitWidth : Math.min(implicitWidth, column.width * 0.66)
                        elide: Text.ElideMiddle
                    }
                }
            }
            Flow {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Chip {
                    visible: preview.kind === "markdown"
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
                    visible: preview.kind === "markdown"
                    kind: "filter"
                    text: "Fuente"
                    selected: pane.showSource
                    onClicked: {
                        pane.showSource = true;
                        selected = Qt.binding(() => pane.showSource);
                    }
                }
                Button {
                    objectName: "expandButton"
                    visible: preview.mode === "file" && preview.kind !== "" && preview.error === ""
                    type: "tonal"
                    icon: "open_in_full"
                    text: "Ampliar"
                    onClicked: root.expandRequested()
                }
                Button {
                    visible: preview.kind === "video" || preview.kind === "audio"
                    type: "tonal"
                    icon: "open_in_new"
                    text: "Seguir en Wysun Player"
                    onClicked: {
                        preview.continueInPlayer(preview.paths[0], root.player.position / 1000);
                        root.player.pause();
                    }
                }
                Button {
                    visible: preview.mode === "file" || preview.mode === "folder"
                    type: "text"
                    icon: "link"
                    text: "Copiar ruta"
                    onClicked: {
                        files.copyText(preview.paths[0]);
                        Window.window.snackbarHost.show({text: "Ruta copiada"});
                    }
                }
            }
        }
    }
}
