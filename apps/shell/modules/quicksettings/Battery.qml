// Adaptado de caelestia-dots/shell/modules/bar/popouts/Battery.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services

RowLayout {
    id: root

    required property var hub
    required property var motion

    spacing: Wysun.Appearance.spaceM
    Services.Battery { id: battery; hub: root.hub }

    Components.MaterialIcon {
        name: battery.glyph
        size: Wysun.Appearance.fontTitle
        color: battery.available && battery.percent < 15 ? Wysun.Appearance.warning : Wysun.Appearance.accent
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        Components.StyledText {
            Layout.fillWidth: true
            text: battery.available ? "Batería · " + battery.percent + "%" : "Batería · No disponible"
            color: Wysun.Appearance.text
            font.pixelSize: Wysun.Appearance.fontBody
            wrapMode: Text.WordWrap
            motion: root.motion
        }
        Components.StyledText {
            Layout.fillWidth: true
            text: battery.available ? battery.status : battery.error
            color: Wysun.Appearance.muted
            font.pixelSize: Wysun.Appearance.fontSmall
            wrapMode: Text.WordWrap
            motion: root.motion
        }
    }
}
