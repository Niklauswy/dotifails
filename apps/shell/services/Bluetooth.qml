// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/bar/popouts/Bluetooth.qml (commit 507d66285e9d9fde9330adc64159cfdebb28c19a).
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Only paired devices are listed; discovery and credential prompts stay out.
import QtQuick

QtObject {
    required property var hub

    readonly property var state: hub ? (hub.states.bluetooth || ({})) : ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "Bluetooth no está disponible"
    readonly property bool enabled: state.enabled || false
    readonly property var devices: state.devices || []
    readonly property int deviceCount: devices.length

    function toggle() { return hub ? hub.act("bluetooth-toggle") : false; }
    function connect(address) { return hub ? hub.act("bluetooth-connect", address) : false; }
    function disconnect(address) { return hub ? hub.act("bluetooth-disconnect", address) : false; }
}
