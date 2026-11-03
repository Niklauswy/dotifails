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

    // The width comes from the text itself, capped by a readable measure: reading `column`'s width here would close
    // a binding loop when only `anchors.centerIn` sets the item's position and the column would shrink to the emblem.
    readonly property int _margin: Theme.padding.extraLarge ?? 0
    readonly property real _contentWidth: Math.max(titleMetrics.advanceWidth, messageMetrics.advanceWidth,
                                                   root.actionText !== "" ? action.implicitWidth : 0)
    implicitWidth: Math.max(Metrics.emptyEmblemSize,
                            Math.min(Metrics.emptyStateMaxWidth, _contentWidth)) + 2 * _margin
    implicitHeight: column.implicitHeight

    TextMetrics {
        id: titleMetrics

        font: titleLabel.font
        text: root.title
    }

    TextMetrics {
        id: messageMetrics

        font: messageLabel.font
        text: root.message
    }

    Column {
        id: column

        anchors.centerIn: parent
        width: Math.max(0, Math.min(root.width - 2 * root._margin, Metrics.emptyStateMaxWidth))
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
            id: titleLabel

            objectName: "emptyTitle"
            width: parent.width
            visible: root.title !== ""
            role: "headline.small"
            text: root.title
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }

        Label {
            id: messageLabel

            objectName: "emptyMessage"
            width: parent.width
            visible: root.message !== ""
            role: "body.medium"
            text: root.message
            color: Theme.m3onSurfaceVariant
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }

        Button {
            id: action

            objectName: "emptyAction"
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.actionText !== ""
            type: "tonal"
            text: root.actionText
            onClicked: root.action()
        }
    }
}
