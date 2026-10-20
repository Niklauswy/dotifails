// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/Nmcli.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
QtObject {
    required property var hub
    readonly property var state: hub.states.network || ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "No disponible"
    readonly property bool wifiEnabled: state.enabled || false
    readonly property var devices: state.devices || []
    readonly property var savedConnections: state.saved || []
    function toggleWifi() { return hub.act("network-toggle"); }
    function connect(uuid) { return hub.act("network-connect", uuid); }
}
