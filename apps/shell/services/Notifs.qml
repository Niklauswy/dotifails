// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/Notifs.qml (solo modelo, sin servidor)
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
QtObject {
    required property var hub
    readonly property var state: hub.states.notifications || ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "No disponible"
    readonly property var list: state.items || []
    readonly property bool dnd: state.paused || false
    function toggleDnd() { return hub.act("notifications-pause"); }
    function remove(id) { return hub.act("notifications-remove", id); }
}
