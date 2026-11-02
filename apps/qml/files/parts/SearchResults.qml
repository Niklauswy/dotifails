// What the search everywhere found (`fileSearch`, the launcher's index): a list with each file's icon, name and folder.
// A click or Enter opens the folder with the file selected; Ctrl+Enter opens the file itself.
import QtQuick
import WysunM3

Item {
    id: root

    property alias currentIndex: list.currentIndex
    signal reveal(string path)
    signal open(string path)

    function step(delta) {
        if (list.count > 0)
            list.currentIndex = Math.max(0, Math.min(list.count - 1, list.currentIndex + delta));
    }

    objectName: "searchResults"

    Connections {
        target: fileSearch

        function onChanged() {
            list.currentIndex = fileSearch.count > 0 ? 0 : -1;
        }
    }

    ListView {
        id: list

        objectName: "searchList"
        anchors.fill: parent
        anchors.leftMargin: FilesMetrics.pagePadding
        anchors.rightMargin: FilesMetrics.pagePadding
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: fileSearch
        highlightMoveDuration: 0

        delegate: Item {
            id: row

            required property int index
            required property string path
            required property string name
            required property string folder
            required property string kind
            required property string icon
            required property string glyph
            required property string role
            required property string badge
            required property string thumb
            readonly property bool current: index === ListView.view.currentIndex

            width: ListView.view.width
            height: Metrics.listItemTwoLine

            Rectangle {
                anchors.fill: parent
                anchors.topMargin: 1
                anchors.bottomMargin: 1
                radius: Theme.rounding.large ?? 0
                color: row.current ? Theme.m3secondaryContainer : "transparent"
            }
            StateLayer {
                anchors.fill: parent
                radius: Theme.rounding.large ?? 0
                tint: row.current ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                onClicked: root.reveal(row.path)
            }
            FileIcon {
                id: rowIcon

                x: Theme.padding.medium ?? 0
                anchors.verticalCenter: parent.verticalCenter
                width: Metrics.listAvatarSize
                height: Metrics.listAvatarSize
                compact: true
                kind: row.kind
                icon: row.icon
                glyph: row.glyph
                role: row.role
                badge: row.badge
                thumb: row.thumb
            }
            Column {
                anchors.left: rowIcon.right
                anchors.leftMargin: Theme.spacing.large ?? 0
                anchors.right: parent.right
                anchors.rightMargin: Theme.padding.medium ?? 0
                anchors.verticalCenter: parent.verticalCenter

                Label {
                    width: parent.width
                    role: "body.large"
                    text: row.name
                    color: row.current ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                    elide: Text.ElideMiddle
                }
                Label {
                    width: parent.width
                    role: "body.small"
                    text: row.folder
                    color: row.current ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                    elide: Text.ElideMiddle
                }
            }
        }
    }

    ScrollBar {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        flickable: list
    }

    EmptyState {
        visible: list.count === 0 && !fileSearch.busy
        anchors.centerIn: parent
        width: Math.min(parent.width, Metrics.dialogMaxWidth)
        emblemShape: fileSearch.query.trim() === "" ? "cookie" : "clover"
        icon: fileSearch.query.trim() === "" ? "search" : "search_off"
        title: fileSearch.query.trim() === "" ? "Busca en todos tus archivos" : "No se encontró nada"
        message: fileSearch.query.trim() === "" ? "Varias palabras afinan: «docs factura pdf»." : "Prueba con otras palabras."
    }
}
