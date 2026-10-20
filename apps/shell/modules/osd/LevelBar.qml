// Derivado de caelestia-dots/shell/modules/osd/Content.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import "../../" as Wysun

Item {
    id: root

    required property var motion
    property real value: 0
    property bool available: true

    implicitHeight: Wysun.Appearance.spaceS

    Rectangle {
        anchors.fill: parent
        radius: Wysun.Appearance.radiusS
        color: Wysun.Appearance.well
    }
    Rectangle {
        width: root.available ? Math.max(0, Math.min(1, root.value)) * parent.width : 0
        height: parent.height
        radius: Wysun.Appearance.radiusS
        color: root.available ? Wysun.Appearance.accent : Wysun.Appearance.disabled
        Behavior on width {
            NumberAnimation {
                duration: root.motion ? root.motion.effectsDuration(160) : 160
                easing.type: Easing.OutCubic
            }
        }
    }
}
