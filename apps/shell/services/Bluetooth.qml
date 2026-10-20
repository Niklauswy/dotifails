// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Bluetooth.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
QtObject {
    required property var hub
    readonly property var state: hub.states.bluetooth || ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "No disponible"
    readonly property bool enabled: state.enabled || false
    readonly property var devices: state.devices || []
    function toggle() { return hub.act("bluetooth-toggle"); }
    function connect(address) { return hub.act("bluetooth-connect", address); }
    function disconnect(address) { return hub.act("bluetooth-disconnect", address); }
}
