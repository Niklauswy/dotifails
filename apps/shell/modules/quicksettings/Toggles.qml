// Adaptado de caelestia-dots/shell/modules/utilities/cards/Toggles.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../services" as Services

GridLayout {
    id: root

    required property var hub
    required property var motion
    property bool preview: false

    columns: width < Wysun.Appearance.spaceXl * 18 ? 1 : 2
    columnSpacing: Wysun.Appearance.spaceS
    rowSpacing: Wysun.Appearance.spaceS

    Services.Nmcli { id: network; hub: root.hub }
    Services.Bluetooth { id: bluetooth; hub: root.hub }

    ControlButton {
        objectName: "wifiToggle"
        Layout.fillWidth: true
        motion: root.motion
        label: network.available ? (network.wifiEnabled ? "Wi-Fi activado" : "Activar Wi-Fi") : "Wi-Fi · No disponible"
        description: network.available ? "Radio inalámbrica de NetworkManager" : network.error
        glyph: "wifi"
        selected: network.wifiEnabled
        enabled: network.available && !root.preview && !root.hub.busy
        onClicked: network.toggleWifi()
    }
    ControlButton {
        objectName: "bluetoothToggle"
        Layout.fillWidth: true
        motion: root.motion
        label: bluetooth.available ? (bluetooth.enabled ? "Bluetooth activado" : "Activar Bluetooth") : "Bluetooth · No disponible"
        description: bluetooth.available ? "Adaptador Bluetooth" : bluetooth.error
        selected: bluetooth.enabled
        enabled: bluetooth.available && !root.preview && !root.hub.busy
        onClicked: bluetooth.toggle()
    }
}
