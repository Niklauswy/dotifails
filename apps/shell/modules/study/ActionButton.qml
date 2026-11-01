import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Pill button of the study surfaces. kind: filled | tonal | text | tertiary (on a tertiary container).
// Its corners tighten while pressed (M3 Expressive shape morph).
StyledRect {
    id: root

    property alias text: label.text
    property string icon
    property string kind: "filled"
    property bool large
    property bool keyFocus
    readonly property color ink: kind === "filled" ? Colours.palette.m3onPrimary
        : kind === "tonal" ? Colours.palette.m3onSecondaryContainer
        : kind === "tertiary" ? Colours.palette.m3tertiaryContainer : Colours.palette.m3primary

    signal clicked

    implicitWidth: content.implicitWidth + (large ? Tokens.padding.extraLarge : Tokens.padding.large) * 2
    implicitHeight: large ? Tokens.padding.extraExtraLarge + Tokens.padding.small : Tokens.padding.extraLarge + Tokens.padding.medium
    radius: mouse.pressed ? (large ? Tokens.rounding.large : Tokens.rounding.medium) : height / 2
    color: kind === "filled" ? Colours.palette.m3primary
        : kind === "tonal" ? Colours.palette.m3secondaryContainer
        : kind === "tertiary" ? Colours.palette.m3onTertiaryContainer : "transparent"

    Behavior on radius {
        Anim {
            type: Anim.FastSpatial
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: root.ink
        opacity: mouse.pressed ? 0.12 : mouse.containsMouse ? 0.08 : 0

        Behavior on opacity {
            Anim {
                type: Anim.FastEffects
            }
        }
    }

    Row {
        id: content

        anchors.centerIn: parent
        spacing: Tokens.spacing.small

        MaterialIcon {
            anchors.verticalCenter: parent.verticalCenter
            visible: !!root.icon
            text: root.icon
            color: root.ink
            fill: 1
            fontStyle: Tokens.font.icon.small
        }

        StyledText {
            id: label

            anchors.verticalCenter: parent.verticalCenter
            color: root.ink
            font: root.large ? Tokens.font.title.medium : Tokens.font.label.large
        }
    }

    FocusRing {
        on: root.keyFocus
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
