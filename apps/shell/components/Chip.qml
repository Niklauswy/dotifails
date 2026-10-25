import QtQuick
import Wysun.Config
import qs.services

// Small pill label: tinted with its accent, or filled with it. `pulsing` breathes the text while waiting.
StyledRect {
    id: root

    property alias text: label.text
    property alias font: label.font
    property color accent: Colours.palette.m3primary
    property color onAccent: Colours.palette.m3onPrimary
    property bool filled
    property bool pulsing

    onPulsingChanged: {
        if (!pulsing)
            label.opacity = 1;
    }

    implicitWidth: label.implicitWidth + Tokens.padding.small * 2
    implicitHeight: label.implicitHeight + Tokens.padding.extraSmall
    radius: Tokens.rounding.full
    color: filled ? accent : Qt.alpha(accent, 0.18)

    Behavior on implicitWidth {
        Anim {
            type: Anim.FastSpatial
        }
    }

    StyledText {
        id: label

        anchors.centerIn: parent
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
