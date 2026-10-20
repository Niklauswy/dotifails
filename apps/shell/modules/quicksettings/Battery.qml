// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Battery.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services
RowLayout {
    id: root
    required property var hub
    spacing: Wysun.Appearance.spaceM
    Services.Battery { id: battery; hub: root.hub }
    Components.MaterialIcon {
        name: battery.available && battery.percent < 15 ? "battery_alert" : "battery_full"
        size: Wysun.Appearance.fontTitle
        color: battery.available && battery.percent < 15 ? Wysun.Appearance.warning : Wysun.Appearance.accent
    }
    Components.StyledText {
        Layout.fillWidth: true
        text: battery.available ? "Batería · " + battery.percent + "% · " + battery.status : battery.error
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
    }
}
