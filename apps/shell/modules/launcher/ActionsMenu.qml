pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.components.effects
import qs.services

// Ctrl+K popover: grouped actions with shortcut keycaps and a filter line at the bottom.
Item {
    id: root

    property var source: []
    property string filterText
    property int current: 0
    property string confirmId
    property real scale: 1
    readonly property font body: Tokens.font.body.builders.medium.size(10.5 * scale).build()

    readonly property var actions: {
        const f = filterText.trim().toLowerCase();
        return f ? source.filter(a => a.title.toLowerCase().includes(f)) : source;
    }

    signal triggered(var action)

    implicitWidth: 310 * scale
    implicitHeight: list.contentHeight + footer.height + Tokens.padding.small * 2 + 1

    onFilterTextChanged: current = 0

    function move(d: int): void {
        if (actions.length)
            current = (current + d + actions.length) % actions.length;
    }

    Elevation {
        anchors.fill: parent
        radius: panel.radius
        level: 4
    }

    Rectangle {
        id: panel

        anchors.fill: parent
        radius: Tokens.rounding.medium
        color: Qt.alpha(Colours.palette.m3surfaceContainerHigh, 0.96)
        border.width: 1
        border.color: Qt.alpha(Colours.palette.m3onSurface, 0.16)
        clip: true

        ListView {
            id: list

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Tokens.padding.small
            height: contentHeight
            interactive: false
            model: root.actions
            delegate: Item {
                id: item

                required property var modelData
                required property int index
                readonly property bool sep: index > 0 && modelData.group !== root.actions[index - 1].group
                readonly property bool on: root.current === index

                width: ListView.view.width
                height: 36 * root.scale + (sep ? Tokens.padding.small + 1 : 0)

                Rectangle {
                    visible: item.sep
                    x: -Tokens.padding.small
                    width: parent.width + Tokens.padding.small * 2
                    height: 1
                    y: Tokens.padding.small / 2
                    color: Qt.alpha(Colours.palette.m3onSurface, 0.1)
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 36 * root.scale
                    radius: Tokens.rounding.small
                    color: item.on ? Qt.alpha(Colours.palette.m3onSurface, 0.1) : "transparent"

                    MaterialIcon {
                        id: ico

                        anchors.left: parent.left
                        anchors.leftMargin: Tokens.padding.small
                        anchors.verticalCenter: parent.verticalCenter
                        text: item.modelData.icon
                        fontStyle: Tokens.font.icon.small
                        color: item.modelData.danger ? Colours.palette.m3error : Colours.palette.m3onSurface
                    }
                    StyledText {
                        anchors.left: ico.right
                        anchors.leftMargin: Tokens.spacing.small
                        anchors.right: keys.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.confirmId === item.modelData.id ? "Press ↵ again to confirm" : item.modelData.title
                        elide: Text.ElideRight
                        font: root.body
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

        Item {
            id: footer

            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 38 * root.scale

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                color: Qt.alpha(Colours.palette.m3onSurface, 0.1)
            }
            StyledText {
                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.medium
                anchors.verticalCenter: parent.verticalCenter
                text: root.filterText || "Search..."
                font: root.body
                color: root.filterText ? Colours.palette.m3onSurface : Colours.palette.m3onSurfaceVariant
            }
        }
    }
}
