pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.components.effects
import qs.services

// Alt+K popover: grouped actions with shortcut keycaps and a filter line on top. It grows out
// of the Actions button (bottom right) with a short spring and fades away when closed.
Item {
    id: root

    property var source: []
    property string filterText
    property int current: 0
    property string confirmId
    property real scale: 1
    property bool open
    readonly property font body: Tokens.font.body.builders.medium.size(10.5 * scale).build()

    readonly property var actions: {
        const f = filterText.trim().toLowerCase();
        return f ? source.filter(a => a.title.toLowerCase().includes(f)) : source;
    }

    signal triggered(var action)

    implicitWidth: 330 * scale
    implicitHeight: list.contentHeight + header.height + Tokens.padding.small * 3

    visible: opacity > 0.01
    opacity: open ? 1 : 0
    transform: Scale {
        origin.x: root.width
        origin.y: root.height
        xScale: 0.86 + 0.14 * root.grow
        yScale: 0.7 + 0.3 * root.grow
    }
    property real grow: open ? 1 : 0

    Behavior on opacity {
        Anim {
            type: Anim.FastEffects
        }
    }
    Behavior on grow {
        Anim {
            type: root.open ? Anim.FastSpatial : Anim.FastEffects
        }
    }

    onFilterTextChanged: current = 0

    function move(d: int): void {
        if (actions.length)
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
        radius: Tokens.rounding.extraLarge
        color: Colours.palette.m3surfaceContainerHigh
        clip: true

        // Filter line: what is typed while the menu is open narrows the actions.
        Rectangle {
            id: header

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Tokens.padding.small
            height: 40 * root.scale
            radius: height / 2
            color: Colours.palette.m3surfaceContainerHighest

            MaterialIcon {
                id: filterIcon

                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.medium
                anchors.verticalCenter: parent.verticalCenter
                text: "bolt"
                fill: 1
                color: Colours.palette.m3primary
                fontStyle: Tokens.font.icon.small
            }
            StyledText {
                anchors.left: filterIcon.right
                anchors.leftMargin: Tokens.spacing.small
                anchors.verticalCenter: parent.verticalCenter
                text: root.filterText || "Search actions…"
                font: root.body
                color: root.filterText ? Colours.palette.m3onSurface : Colours.palette.m3onSurfaceVariant
            }
        }

        ListView {
            id: list

            anchors.top: header.bottom
            anchors.topMargin: Tokens.padding.small
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: Tokens.padding.small
            anchors.rightMargin: Tokens.padding.small
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
                height: 40 * root.scale + (sep ? Tokens.padding.small + 1 : 0)

                Rectangle {
                    visible: item.sep
                    x: Tokens.padding.medium
                    width: parent.width - Tokens.padding.medium * 2
                    height: 1
                    y: Tokens.padding.small / 2
                    color: Colours.palette.m3outlineVariant
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 40 * root.scale
                    radius: item.on ? Tokens.rounding.large : height / 2
                    color: item.on ? (item.modelData.danger ? Colours.palette.m3errorContainer : Colours.palette.m3secondaryContainer) : "transparent"

                    Behavior on color {
                        CAnim {}
                    }

                    MaterialIcon {
                        id: ico

                        anchors.left: parent.left
                        anchors.leftMargin: Tokens.padding.medium
                        anchors.verticalCenter: parent.verticalCenter
                        text: item.modelData.icon
                        fill: item.on ? 1 : 0
                        fontStyle: Tokens.font.icon.small
                        color: item.modelData.danger ? (item.on ? Colours.palette.m3onErrorContainer : Colours.palette.m3error) : item.on ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                    }
                    StyledText {
                        anchors.left: ico.right
                        anchors.leftMargin: Tokens.spacing.medium
                        anchors.right: keys.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.confirmId === item.modelData.id ? "Press ↵ again to confirm" : item.modelData.title
                        elide: Text.ElideRight
                        font: root.body
                        color: item.modelData.danger ? (item.on ? Colours.palette.m3onErrorContainer : Colours.palette.m3error) : item.on ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
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
                        cursorShape: Qt.PointingHandCursor
                        onPositionChanged: root.current = item.index
                        onClicked: root.triggered(item.modelData)
                    }
                }
            }
        }
    }
}
