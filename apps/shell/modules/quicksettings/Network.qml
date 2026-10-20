// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Network.qml
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
    required property var controller
    spacing: Wysun.Appearance.spaceS
    Services.Nmcli { id: network; hub: root.hub }
    Components.StyledText { text: "Red"; font.pixelSize: Wysun.Appearance.fontHeading }
    Components.StyledText {
        Layout.fillWidth: true
        text: network.available ? "Conexiones guardadas. Las contraseñas se gestionan en Conexiones." : network.error
        wrapMode: Text.WordWrap
        color: Wysun.Appearance.muted
    }
    Repeater {
        model: network.devices
        Components.StyledText {
            required property var modelData
            Layout.fillWidth: true
            text: modelData.device + " · " + (modelData.connection === "--" ? "Sin conexión" : modelData.connection)
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }
    }
    Repeater {
        model: network.savedConnections
        ControlButton {
            required property var modelData
            Layout.fillWidth: true
            motion: root.motion
            label: "Conectar · " + modelData.name
            enabled: network.available && !root.hub.busy
            onClicked: network.connect(modelData.uuid)
        }
    }
    ControlButton {
        Layout.fillWidth: true
        motion: root.motion
        label: "Abrir Conexiones"
        onClicked: root.controller.launch("connections")
    }
}
