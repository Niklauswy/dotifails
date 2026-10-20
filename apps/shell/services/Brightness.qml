// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/Brightness.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
QtObject {
    required property var hub
    readonly property var state: hub.states.brightness || ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "No disponible"
    readonly property real brightness: (state.percent || 0) / 100
    function setBrightness(value) { return hub.act("brightness-set", Math.max(5, Math.round(value * 100))); }
}
