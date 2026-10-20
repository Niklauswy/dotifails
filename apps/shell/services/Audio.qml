// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/Audio.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
QtObject {
    required property var hub
    readonly property var state: hub.states.audio || ({})
    readonly property bool available: state.available === true
    readonly property string error: state.error || "No disponible"
    readonly property real volume: (state.percent || 0) / 100
    readonly property bool muted: state.muted || false
    function setVolume(value) { return hub.act("audio-set", Math.round(value * 100)); }
    function toggleMuted() { return hub.act("audio-mute"); }
}
