import QtQuick
import Wysun.Config
import qs.services

// Small pill label: tinted with its accent, or filled with it, with an optional leading `icon`.
// `pulsing` breathes the text while waiting.
StyledRect {
    id: root

    property alias text: label.text
    property alias font: label.font
    // Material symbol drawn before the text; empty for a text-only chip.
    property string icon
    property color accent: Colours.palette.m3primary
    property color onAccent: Colours.palette.m3onPrimary
    property bool filled
    property bool pulsing

    onPulsingChanged: {
        if (!pulsing)
            label.opacity = 1;
    }

    implicitWidth: content.implicitWidth + (icon ? Tokens.padding.medium : Tokens.padding.small) * 2
    implicitHeight: content.implicitHeight + (icon ? Tokens.padding.small : Tokens.padding.extraSmall)
    radius: Tokens.rounding.full
    color: filled ? accent : Qt.alpha(accent, 0.18)

    Behavior on implicitWidth {
        Anim {
            type: Anim.FastSpatial
        }
    }

    Row {
        id: content

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall

        MaterialIcon {
            anchors.verticalCenter: parent.verticalCenter
            visible: !!root.icon
            text: root.icon
            fill: 1
            color: label.color
            fontStyle: Tokens.font.icon.small
        }

        StyledText {
            id: label

            anchors.verticalCenter: parent.verticalCenter
            font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
            color: root.filled ? root.onAccent : root.accent

            SequentialAnimation on opacity {
                running: root.pulsing
                loops: Animation.Infinite

                NumberAnimation {
                    to: 0.45
                    duration: Tokens.anim.durations.expressiveDefaultSpatial
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    to: 1
                    duration: Tokens.anim.durations.expressiveDefaultSpatial
                    easing.type: Easing.InOutSine
                }
            }
        }
    }
}
