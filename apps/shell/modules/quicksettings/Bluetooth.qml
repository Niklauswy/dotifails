// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Bluetooth.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services
ColumnLayout {
    id: root
    required property var hub
    required property var motion
    spacing: Wysun.Appearance.spaceS
    Services.Bluetooth { id: bluetooth; hub: root.hub }
    Components.StyledText { text: "Bluetooth"; font.pixelSize: Wysun.Appearance.fontHeading }
    Components.StyledText {
        Layout.fillWidth: true
        text: bluetooth.available ? "Dispositivos emparejados · sin búsqueda automática" : bluetooth.error
        color: Wysun.Appearance.muted
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: bluetooth.devices
        ColumnLayout {
            required property var modelData
            Layout.fillWidth: true
            Components.StyledText { text: parent.modelData.name; textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            RowLayout {
                Layout.fillWidth: true
                ControlButton {
                    Layout.fillWidth: true
                    motion: root.motion
                    label: "Conectar"
                    enabled: bluetooth.enabled && !root.hub.busy
                    onClicked: bluetooth.connect(modelData.address)
                }
                ControlButton {
                    Layout.fillWidth: true
                    motion: root.motion
                    label: "Desconectar"
                    enabled: bluetooth.enabled && !root.hub.busy
                    onClicked: bluetooth.disconnect(modelData.address)
                }
            }
        }
    }
}
