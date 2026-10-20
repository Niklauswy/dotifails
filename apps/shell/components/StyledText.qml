// Derivado de caelestia-dots/shell/components/StyledText.qml (GPL-3.0), modificado para Wysun.
// Fuente: caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import "../" as Wysun

Text {
    id: root
    property var motion
    property bool animate: false
    renderType: Text.NativeRendering
    textFormat: Text.PlainText
    color: Wysun.Appearance.text
    font.family: Wysun.Appearance.fontFamily

    Behavior on color {
        ColorAnimation {
            duration: root.motion ? root.motion.effectsDuration(160) : 160
            easing.type: Easing.OutCubic
        }
    }

    Behavior on text {
        enabled: root.animate && (!root.motion || !root.motion.reducedMotion)
        SequentialAnimation {
            Anim { motion: root.motion; type: Anim.FastEffects; target: root; property: "opacity"; to: 0 }
            PropertyAction { }
            Anim { motion: root.motion; type: Anim.DefaultEffects; target: root; property: "opacity"; to: 1 }
        }
    }
}
