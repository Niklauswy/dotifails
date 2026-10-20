// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Bluetooth.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services

SectionCard {
    id: root

    required property var hub
    property bool preview: false

    title: "Bluetooth"
    subtitle: bluetooth.available
        ? (bluetooth.devices.length > 0 ? "Dispositivos emparejados · sin búsqueda automática" : "Sin dispositivos emparejados")
        : bluetooth.error

    Services.Bluetooth { id: bluetooth; hub: root.hub }

    Repeater {
        model: bluetooth.available ? bluetooth.devices : []
        ColumnLayout {
            id: device
            required property var modelData
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceXs
            Components.StyledText {
                Layout.fillWidth: true
                text: device.modelData.name
                textFormat: Text.PlainText
                color: Wysun.Appearance.text
                font.pixelSize: Wysun.Appearance.fontSmall
                wrapMode: Text.WordWrap
                motion: root.motion
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Wysun.Appearance.spaceS
                ControlButton {
                    Layout.fillWidth: true
                    motion: root.motion
                    label: "Conectar"
                    description: "Conecta " + device.modelData.name
                    enabled: bluetooth.enabled && !root.preview && !root.hub.busy
                    onClicked: bluetooth.connect(device.modelData.address)
                }
                ControlButton {
                    Layout.fillWidth: true
                    motion: root.motion
                    label: "Desconectar"
                    description: "Desconecta " + device.modelData.name
                    enabled: bluetooth.enabled && !root.preview && !root.hub.busy
                    onClicked: bluetooth.disconnect(device.modelData.address)
                }
            }
        }
    }

    ControlButton {
        visible: !bluetooth.available
        Layout.fillWidth: true
        motion: root.motion
        label: "Bluetooth · No disponible"
        description: bluetooth.error
        enabled: false
    }
}
