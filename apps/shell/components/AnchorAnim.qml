// Derivado de caelestia-dots/shell/components/AnchorAnim.qml (GPL-3.0), modificado para Wysun.
// Fuente: caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick

AnchorAnimation {
    property var motion
    duration: motion ? motion.morph : 280
    easing.type: Easing.BezierSpline
    easing.bezierCurve: motion ? motion.emphasizedCurve : [0.2, 0, 0, 1, 1, 1]
}
