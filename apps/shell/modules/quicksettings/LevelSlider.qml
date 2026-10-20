// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/osd/Content.qml; modules/bar/popouts/AudioPopout.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Controls
import "../../" as Wysun
Slider {
    id: root
    from: 0
    to: 100
    stepSize: 1
    implicitHeight: Wysun.Appearance.fontBody + Wysun.Appearance.spaceL * 2
    padding: Wysun.Appearance.spaceS
    Accessible.name: "Nivel"
    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: Wysun.Appearance.spaceS
        radius: Wysun.Appearance.radiusS
        color: Wysun.Appearance.well
        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: root.enabled ? Wysun.Appearance.accent : Wysun.Appearance.disabled
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: Wysun.Appearance.spaceXl
        height: Wysun.Appearance.spaceXl
        radius: Wysun.Appearance.radiusL
        color: root.enabled ? Wysun.Appearance.accent : Wysun.Appearance.disabled
        border.width: root.activeFocus ? Wysun.Appearance.focusWidth : 0
        border.color: Wysun.Appearance.text
    }
}
