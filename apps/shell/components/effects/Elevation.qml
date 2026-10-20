import QtQuick
import QtQuick.Effects
import qs.components
import qs.services

RectangularShadow {
    property int level
    // Per-corner radii need newer Qt's RectangularShadow; Qt 6.9 shadows use one radius.
    property real topLeftRadius: radius
    property real topRightRadius: radius
    property real bottomLeftRadius: radius
    property real bottomRightRadius: radius
    property real dp: [0, 1, 3, 6, 8, 12][level]

    color: Qt.alpha(Colours.palette.m3shadow, 0.7)
    blur: (dp * 5) ** 0.7
    spread: -dp * 0.3 + (dp * 0.1) ** 2
    offset.y: dp / 2

    Behavior on dp {
        Anim {
            type: Anim.SlowEffects
        }
    }
}
