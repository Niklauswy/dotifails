// Derivado de caelestia-dots/shell/components/StyledRect.qml (GPL-3.0), modificado para Wysun.
// Fuente: caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick

Rectangle {
    id: root
    property var motion
    color: "transparent"

    Behavior on color {
        ColorAnimation {
            duration: root.motion ? root.motion.effectsDuration(160) : 160
            easing.type: Easing.OutCubic
        }
    }
}
