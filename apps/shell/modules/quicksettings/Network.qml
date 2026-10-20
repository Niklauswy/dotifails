// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Network.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "../../services" as Services

SectionCard {
    id: root

    required property var hub
    required property var controller
    property bool preview: false

    title: "Red"
    subtitle: network.available ? network.summary : network.error

    Services.Nmcli { id: network; hub: root.hub }

    Repeater {
        model: network.available ? network.devices : []
        RowLayout {
            id: device
            required property var modelData
            Layout.fillWidth: true
            spacing: Wysun.Appearance.spaceS
            Components.StyledText {
                Layout.fillWidth: true
                text: device.modelData.device + " · " + (device.modelData.connection === "--" ? "Sin conexión" : device.modelData.connection)
                textFormat: Text.PlainText
                color: Wysun.Appearance.text
                font.pixelSize: Wysun.Appearance.fontSmall
                wrapMode: Text.WordWrap
                motion: root.motion
            }
        }
    }

    Repeater {
        model: network.available ? network.savedConnections : []
        ControlButton {
            required property var modelData
            Layout.fillWidth: true
            motion: root.motion
            label: "Conectar · " + modelData.name
            description: "Perfil guardado de NetworkManager"
            enabled: !root.preview && !root.hub.busy
            onClicked: network.connect(modelData.uuid)
        }
    }

    ControlButton {
        Layout.fillWidth: true
        motion: root.motion
        label: "Abrir Conexiones"
        description: "Redes, dispositivos y VPN en la ventana de Wysun"
        enabled: !root.preview
        onClicked: root.controller.launch("connections")
    }

    Components.StyledText {
        visible: !network.available
        Layout.fillWidth: true
        text: network.error
        color: Wysun.Appearance.disabled
        font.pixelSize: Wysun.Appearance.fontSmall
        wrapMode: Text.WordWrap
        motion: root.motion
    }
}
