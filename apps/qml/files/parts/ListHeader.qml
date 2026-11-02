// The column titles of the list (F-22): clicking one sorts by it, clicking it again reverses the order.
import QtQuick
import WysunM3

Item {
    id: root

    property var model                      // FolderModel
    property bool wide: true
    readonly property real nameWidth: width - 2 * (Theme.padding.medium ?? 0) - FilesMetrics.rowIcon - FilesMetrics.sizeColumn - (wide ? FilesMetrics.dateColumn + FilesMetrics.typeColumn : 0) - (wide ? 4 : 2) * (Theme.spacing.medium ?? 0)

    height: Metrics.chipHeight

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.padding.medium ?? 0
        anchors.rightMargin: Theme.padding.medium ?? 0
        spacing: Theme.spacing.medium ?? 0

        Item {
            width: FilesMetrics.rowIcon
            height: parent.height
        }
        Repeater {
            model: [{key: "name", text: "Nombre"}, {key: "modified", text: "Modificado", wide: true}, {key: "size", text: "Tamaño"}, {key: "kind", text: "Tipo", wide: true}]

            Item {
                id: column

                required property var modelData
                readonly property bool active: root.model && root.model.sortKey === modelData.key

                objectName: "column-" + modelData.key
                visible: !modelData.wide || root.wide
                height: root.height
                width: modelData.key === "name" ? root.nameWidth : modelData.key === "size" ? FilesMetrics.sizeColumn : modelData.key === "modified" ? FilesMetrics.dateColumn : FilesMetrics.typeColumn

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacing.extraSmall ?? 0

                    Label {
                        role: "label.large"
                        text: column.modelData.text
                        color: column.active ? Theme.m3onSurface : Theme.m3onSurfaceVariant
                    }
                    Icon {
                        visible: column.active
                        name: root.model && root.model.descending ? "arrow_downward" : "arrow_upward"
                        size: Metrics.buttonIconSize
                        color: Theme.m3onSurface
                    }
                }
                StateLayer {
                    anchors.fill: parent
                    radius: Theme.rounding.small ?? 0
                    onClicked: root.model.sortBy(column.modelData.key, column.active ? !root.model.descending : false)
                }
            }
        }
    }
}
