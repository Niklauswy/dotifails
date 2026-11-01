import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Faint frame around the screen for as long as a session runs, plus the light that runs around it.
Item {
    id: root

    property bool on
    property alias sweepTick: sweep.tick
    property alias shortSweep: sweep.quick

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: Tokens.padding.extraSmall / 2
        border.color: Qt.alpha(Colours.palette.m3primary, 0.32)
        opacity: root.on ? 1 : 0

        Behavior on opacity {
            Anim {
                type: Anim.SlowEffects
            }
        }
    }

    EdgeSweep {
        id: sweep

        anchors.fill: parent
        radius: 0
    }
}
