pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.components.effects
import qs.services

// Ctrl+K popover with the secondary actions of the selected item.
Item {
    id: root

    property var actions: []
    property int current: 0
    property string confirmId
    property real scale: 1

    signal triggered(var action)

    implicitWidth: 340 * scale
    implicitHeight: list.contentHeight + Tokens.padding.small * 2

    function move(d: int): void {
        current = (current + d + actions.length) % actions.length;
    }

    Elevation {
        anchors.fill: parent
        radius: panel.radius
        level: 3
    }

    Rectangle {
        id: panel

        anchors.fill: parent
        radius: Tokens.rounding.medium
        color: Colours.palette.m3surfaceContainerHigh
        border.width: 1
        border.color: Colours.palette.m3outlineVariant

        ListView {
            id: list

            anchors.fill: parent
            anchors.margins: Tokens.padding.small
            interactive: false
            currentIndex: root.current
            model: root.actions
            highlightMoveDuration: Tokens.anim.durations.expressiveFastEffects
            highlight: Rectangle {
                radius: Tokens.rounding.small
                color: Colours.palette.m3secondaryContainer
            }
            delegate: Item {
                id: item

                required property var modelData
                required property int index

                width: ListView.view.width
                height: 36 * root.scale

                MaterialIcon {
                    id: ico

                    anchors.left: parent.left
                    anchors.leftMargin: Tokens.padding.small
                    anchors.verticalCenter: parent.verticalCenter
                    text: item.modelData.icon
                    fontStyle: Tokens.font.icon.small
                    color: item.modelData.danger ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                }
                StyledText {
                    anchors.left: ico.right
                    anchors.leftMargin: Tokens.spacing.small
                    anchors.right: keys.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.confirmId === item.modelData.id ? "Press ↵ again to confirm" : item.modelData.title
                    elide: Text.ElideRight
                    font: Tokens.font.body.medium
                    color: item.modelData.danger ? Colours.palette.m3error : Colours.palette.m3onSurface
                }
                Keycaps {
                    id: keys

                    anchors.right: parent.right
                    anchors.rightMargin: Tokens.padding.small
                    anchors.verticalCenter: parent.verticalCenter
                    keys: item.modelData.shortcut ? item.modelData.shortcut.split(" ") : []
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onPositionChanged: root.current = item.index
                    onClicked: root.triggered(item.modelData)
                }
            }
        }
    }
}
