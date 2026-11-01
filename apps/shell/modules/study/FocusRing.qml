import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Keyboard focus outline around its parent (M3 focus indicator), shown while `on`.
Rectangle {
    property bool on
    property real gap: Tokens.padding.extraSmall - 1

    anchors.fill: parent
    anchors.margins: -gap
    radius: (parent.radius ?? 0) + gap
    color: "transparent"
    border.width: 2
    border.color: Colours.palette.m3primary
    opacity: on ? 1 : 0

    Behavior on opacity {
        Anim {
            type: Anim.FastEffects
        }
    }
}
