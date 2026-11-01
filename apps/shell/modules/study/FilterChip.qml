import QtQuick
import Wysun.Config
import qs.components
import qs.services

// M3 filter chip: outlined, or filled with a check mark when selected. `icon` replaces the check (e.g. "add").
StyledRect {
    id: root

    property alias text: label.text
    property string icon
    property bool selected
    readonly property bool lead: selected || !!icon

    signal clicked

    implicitWidth: label.implicitWidth + Tokens.padding.large * 2 + (lead ? mark.implicitWidth + Tokens.spacing.small - Tokens.padding.small : 0)
    implicitHeight: Tokens.padding.extraLarge + Tokens.padding.extraSmall
    radius: Tokens.rounding.small
    color: selected ? Colours.palette.m3secondaryContainer : "transparent"
    border.width: selected ? 0 : 1
    border.color: Colours.palette.m3outlineVariant

    Behavior on implicitWidth {
        Anim {
            type: Anim.FastSpatial
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: Colours.palette.m3onSurface
        opacity: mouse.pressed ? 0.12 : mouse.containsMouse ? 0.08 : 0
    }

    MaterialIcon {
        id: mark

        anchors.verticalCenter: parent.verticalCenter
        x: Tokens.padding.small
        text: root.icon || "check"
        opacity: root.lead ? 1 : 0
        color: root.selected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
        fontStyle: Tokens.font.icon.small

        Behavior on opacity {
            Anim {
                type: Anim.FastEffects
            }
        }
    }

    StyledText {
        id: label

        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: Tokens.padding.large
        color: root.selected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
        font: Tokens.font.label.large
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
