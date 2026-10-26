// An empty or first-run state: an expressive ShapeEmblem that springs in (slow spatial; still with reduced
// motion), a title, a message and an optional tonal action. Centre it in the area that would show content.
import QtQuick
import WysunM3

Item {
    id: root

    property string emblemShape: "cookie"
    property string icon
    property string title
    property string message
    property string actionText
    property color emblemColor: Theme.m3secondaryContainer
    property color emblemIconColor: Theme.m3onSecondaryContainer

    signal action

    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight

    Column {
        id: column

        anchors.centerIn: parent
        width: Math.min(parent.width - 2 * (Theme.padding.extraLarge ?? 0), Metrics.textFieldMinWidth * 2)
        spacing: Theme.spacing.large ?? 0

        ShapeEmblem {
            id: emblem

            objectName: "emptyEmblem"
            anchors.horizontalCenter: parent.horizontalCenter
            size: Metrics.emptyEmblemSize
            shape: root.emblemShape
            icon: root.icon
            color: root.emblemColor
            iconColor: root.emblemIconColor
            morphOnHover: true
            scale: Motion.reduced ? 1 : Metrics.emptyEmblemEnterScale
            rotation: 0

            Component.onCompleted: {
                if (!Motion.reduced) {
                    enter.start();
                    turn.start();
                }
            }

            Anim {
                id: enter

                target: emblem
                property: "scale"
                to: 1
                kind: "slowSpatial"
            }
            Anim {
                id: turn

                target: emblem
                property: "rotation"
                from: Metrics.emptyEmblemEnterTurn
                to: 0
                kind: "slowSpatial"
            }
        }

        Label {
            width: parent.width
            visible: root.title !== ""
            role: "headline.small"
            text: root.title
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }

        Label {
            width: parent.width
            visible: root.message !== ""
            role: "body.medium"
            text: root.message
            color: Theme.m3onSurfaceVariant
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }

        Button {
            objectName: "emptyAction"
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.actionText !== ""
            type: "tonal"
            text: root.actionText
            onClicked: root.action()
        }
    }
}
