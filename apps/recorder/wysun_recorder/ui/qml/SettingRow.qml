// One setting: its name and explanation on the left, its control (a Component) on the right. A row with no
// control is plain information (the shortcuts).
import QtQuick
import WysunM3

Item {
    id: root

    property string title
    property string hint
    property Component control
    readonly property Item controlItem: loader.item

    width: parent ? parent.width : implicitWidth
    implicitHeight: Math.max(hint !== "" ? Metrics.listItemTwoLine : Metrics.listItemOneLine, texts.implicitHeight + 2 * (Theme.padding.small ?? 0))
    height: implicitHeight

    Column {
        id: texts

        anchors.left: parent.left
        anchors.leftMargin: Theme.padding.medium ?? 0
        anchors.right: loader.left
        anchors.rightMargin: Theme.padding.medium ?? 0
        anchors.verticalCenter: parent.verticalCenter

        Label {
            width: parent.width
            text: root.title
            role: "body.large"
            wrapMode: Text.Wrap
        }
        Label {
            width: parent.width
            visible: root.hint !== ""
            text: root.hint
            role: "body.medium"
            color: Theme.m3onSurfaceVariant
            wrapMode: Text.Wrap
        }
    }

    Loader {
        id: loader

        anchors.right: parent.right
        anchors.rightMargin: Theme.padding.medium ?? 0
        anchors.verticalCenter: parent.verticalCenter
        sourceComponent: root.control
    }
}
