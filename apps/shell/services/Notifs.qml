// Adaptado de caelestia-dots/shell/services/Notifs.qml (GPL-3.0), solo el
// modelo de presentación; no se porta NotificationServer. Fuente:
// caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Dunst remains the one and only server. Reading its history never creates a
// second bus owner and never shows a toast from Quickshell.
import QtQuick

QtObject {
    required property var hub

    readonly property var state: hub ? (hub.states.notifications || ({})) : ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "Dunst no está disponible"
    readonly property var list: state.items || []
    readonly property bool dnd: state.paused || false
    readonly property int pauseLevel: state.pauseLevel || 0

    function toggleDnd() { return hub ? hub.act("notifications-pause") : false; }
    function remove(id) { return hub ? hub.act("notifications-remove", id) : false; }
    function clear() { return hub ? hub.act("notifications-clear") : false; }
}
