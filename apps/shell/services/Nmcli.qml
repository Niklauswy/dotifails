// Adaptado de caelestia-dots/shell/services/Nmcli.qml (GPL-3.0), modificado
// para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Read-only view over a bounded provider snapshot; no nmcli call per frame.
import QtQuick

QtObject {
    required property var hub

    readonly property var state: hub ? (hub.states.network || ({})) : ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "NetworkManager no está disponible"
    readonly property bool wifiEnabled: state.enabled || false
    readonly property var devices: state.devices || []
    readonly property var savedConnections: state.saved || []
    readonly property string summary: {
        if (!available) return error;
        var active = devices.filter(function(device) { return device.connection && device.connection !== "--"; });
        return active.length > 0 ? active[0].connection + " · " + active[0].device : "Sin conexión";
    }

    function toggleWifi() { return hub ? hub.act("network-toggle") : false; }
    function connect(uuid) { return hub ? hub.act("network-connect", uuid) : false; }
}
