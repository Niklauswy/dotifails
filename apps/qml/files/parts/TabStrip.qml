// The tabs of the window (F-13), shown when there is more than one: a pill per tab with its folder and a close
// button; middle click closes; «+» opens a new one (Ctrl+T).
import QtQuick
import WysunM3

Item {
    id: root

    property var tabs: []
    property int currentIndex
    signal selected(int index)
    signal closed(int index)
    signal added

    implicitHeight: FilesMetrics.tabHeight

    ListView {
        id: strip

        objectName: "tabStrip"
        anchors.left: parent.left
        anchors.right: add.left
        anchors.rightMargin: Theme.spacing.small ?? 0
        height: parent.height
        orientation: ListView.Horizontal
        spacing: Theme.spacing.small ?? 0
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.tabs
        currentIndex: root.currentIndex
        highlightFollowsCurrentItem: false
        onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)

        delegate: Item {
            id: pill

            required property var modelData
            required property int index
            readonly property bool active: index === root.currentIndex

            objectName: "tab-" + index
            width: Math.min(FilesMetrics.tabMaxWidth, row.implicitWidth + 2 * (Theme.padding.medium ?? 0))
            height: root.height

            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: pill.active ? Theme.m3secondaryContainer : "transparent"

                Behavior on color {
                    CAnim {
                        kind: "fastEffects"
                    }
                }
            }
            StateLayer {
                anchors.fill: parent
                radius: height / 2
                tint: pill.active ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                mouseArea.acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                onClicked: mouse => mouse.button === Qt.MiddleButton ? root.closed(pill.index) : root.selected(pill.index)
            }
            Row {
                id: row

                anchors.verticalCenter: parent.verticalCenter
                x: Theme.padding.medium ?? 0
                width: parent.width - 2 * x
                spacing: Theme.spacing.small ?? 0

                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: "folder"
                    filled: pill.active
                    size: Metrics.buttonIconSize
                    color: pill.active ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, FilesMetrics.tabMaxWidth - 2 * (Theme.padding.medium ?? 0) - 2 * Metrics.buttonIconSize - 2 * parent.spacing)
                    role: "label.large"
                    text: pill.modelData.title
                    color: pill.active ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                    elide: Text.ElideMiddle
                }
                Item {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Metrics.buttonIconSize
                    height: width

                    Icon {
                        anchors.centerIn: parent
                        name: "close"
                        size: Metrics.buttonIconSize
                        color: pill.active ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                    }
                    StateLayer {
                        anchors.fill: parent
                        anchors.margins: -(Theme.spacing.extraSmall ?? 0)
                        radius: width / 2
                        onClicked: root.closed(pill.index)
                    }
                }
            }
        }
    }
    IconButton {
        id: add

        objectName: "newTabButton"
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        icon: "add"
        onClicked: root.added()

        Tooltip {
            text: "Nueva pestaña · Ctrl+T"
        }
    }
}
